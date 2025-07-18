import websocket
import threading
import json
import time
import sys
import os
import queue
import requests
from typing import Dict, List, Optional, Any

class NeuroSityController:
    def __init__(self):
        # WebSocket server runs on port 4000
        self.ws_url = "ws://localhost:4000"
        self.available_datasets = []
        self.current_dataset = None
        self.ws = None
        self.ws_thread = None
        self.running = False
        self.message_queue = queue.Queue()
        self.dataset_selected = threading.Event()
        self.initialized = threading.Event()
        
    def connect(self):
        """Connect to the WebSocket server"""
        try:
            self.ws = websocket.WebSocketApp(
                self.ws_url,
                on_message=self.on_message,
                on_error=self.on_error,
                on_close=self.on_close,
                on_open=self.on_open
            )
            self.running = True
            self.ws_thread = threading.Thread(target=self.ws.run_forever)
            self.ws_thread.daemon = True
            self.ws_thread.start()
            
            # Wait for the connection to be established and initialized
            if not self.initialized.wait(timeout=10):
                print("Timed out waiting for WebSocket initialization")
                return False
                
            return True
        except Exception as e:
            print(f"Failed to connect to WebSocket: {e}")
            return False
    
    def fetch_datasets(self):
        """Wait for the initial dataset list from WebSocket"""
        try:
            # Wait for the initial message with datasets (up to 5 seconds)
            if not self.initialized.wait(timeout=5):
                print("Timed out waiting for initial dataset list")
                return False
            return True
        except Exception as e:
            print(f"Failed to fetch datasets: {e}")
            return False
    
    def select_dataset(self, dataset_info):
        """Select a dataset by sending a WebSocket message"""
        try:
            if not self.ws or not self.running:
                print("WebSocket is not connected")
                return False
                
            print(f"Attempting to select dataset: {dataset_info.get('name')}")
            print(f"Dataset path: {dataset_info.get('path')}")
            
            # Reset the selection event
            self.dataset_selected.clear()
            
            # Prepare the select message with file path
            select_msg = {
                "type": "selectDataset",
                "filePath": dataset_info.get('path'),
                "datasetIndex": dataset_info.get('index', 1)  # Add index as fallback
            }
            
            print(f"[DEBUG] Sending select message: {select_msg}")
            
            # Send the message
            self.ws.send(json.dumps(select_msg))
            
            # Wait for confirmation (with timeout)
            timeout = 10  # Increased timeout
            print(f"Waiting up to {timeout} seconds for dataset selection confirmation...")
            
            if self.dataset_selected.wait(timeout=timeout):
                print(f"Successfully selected dataset: {self.current_dataset}")
                return True
            else:
                print("Timed out waiting for dataset selection confirmation")
                print("This could be due to:")
                print("1. The emulator not responding to the selectDataset message")
                print("2. The WebSocket connection being interrupted")
                print("3. The dataset selection not triggering a response")
                return False
                
        except Exception as e:
            print(f"Error selecting dataset: {str(e)}")
            return False
    
    def on_message(self, ws, message):
        """Handle incoming WebSocket messages"""
        try:
            print(f"\n[DEBUG] Received message: {message}")  # Debug log
            data = json.loads(message)
            message_type = data.get('type')
            
            if message_type == 'init':
                # Handle initial message with dataset list
                print("[DEBUG] Received init message with datasets")  # Debug log
                self.available_datasets = data.get('availableDatasets', {})
                self.initialized.set()
                
            elif message_type == 'datasetSelected':
                # Handle dataset selection confirmation
                print(f"[DEBUG] Received datasetSelected: {data}")  # Debug log
                self.current_dataset = data.get('name', data.get('path', 'Unknown Dataset'))
                self.dataset_selected.set()
                
            elif message_type == 'status':
                # Handle status messages
                status_msg = data.get('message', '')
                print(f"\nStatus: {status_msg}")
                
                # Check if this is a dataset selection status
                if 'dataset' in status_msg.lower() and 'selected' in status_msg.lower():
                    self.dataset_selected.set()
                
            elif message_type == 'data':
                # Handle data stream
                self._process_data_message(data)
            
            # Add the message to the queue for the main thread
            self.message_queue.put(data)
            
        except json.JSONDecodeError:
            print(f"[DEBUG] Received non-JSON message: {message}")
        except Exception as e:
            print(f"[DEBUG] Error processing message: {str(e)}")
            
        except Exception as e:
            print(f"Error processing message: {e}")
    
    def _process_data_message(self, data: Dict[str, Any]) -> None:
        """Process incoming data messages"""
        os.system('cls' if os.name == 'nt' else 'clear')
        print("NeuroSity Data Receiver (Press Ctrl+C to exit)\n")
        print(f"Current Dataset: {self.current_dataset or 'None'}\n")
        print("Latest Data:")
        print(json.dumps(data, indent=2))
    
    def on_error(self, ws, error):
        print(f"WebSocket error: {error}")
        self.running = False
    
    def on_close(self, ws, close_status_code, close_msg):
        print(f"WebSocket connection closed: {close_status_code} - {close_msg}")
        self.running = False
    
    def on_open(self, ws):
        print("Connected to NeuroSity emulator")
        # Request initial data
        ws.send(json.dumps({"type": "getDatasets"}))
    
    def close(self):
        """Clean up WebSocket connection"""
        self.running = False
        if self.ws:
            self.ws.close()
        if self.ws_thread:
            self.ws_thread.join(timeout=2)
        # Clear any remaining messages
        while not self.message_queue.empty():
            try:
                self.message_queue.get_nowait()
            except queue.Empty:
                break

# Global controller instance
controller = NeuroSityController()

# Connect to the emulator
if not controller.connect() or not controller.fetch_datasets():
    print("Failed to connect to NeuroSity emulator. Make sure it's running.")
    sys.exit(1)

def print_help():
    print("\nAvailable commands:")
    print("  list    - List available datasets")
    print("  select <number> - Select and start a dataset")
    print("  help    - Show this help")
    print("  exit    - Exit the program")

def flatten_datasets(available_datasets):
    """Convert the nested dataset structure to a flat list with category info"""
    flat_list = []
    for category, datasets in available_datasets.items():
        for dataset in datasets:
            flat_list.append({
                'category': category,
                'name': dataset.get('filename', 'Unknown'),
                'path': dataset.get('path', ''),
                'index': len(flat_list) + 1  # 1-based index
            })
    return flat_list

def list_available_datasets():
    if not controller.available_datasets:
        print("No datasets available. Waiting for data from server...")
        return
        
    print("\nAvailable datasets:")
    flat_datasets = flatten_datasets(controller.available_datasets)
    
    # Group by category for display
    categories = {}
    for ds in flat_datasets:
        if ds['category'] not in categories:
            categories[ds['category']] = []
        categories[ds['category']].append(ds)
    
    # Print datasets by category
    for category, datasets in categories.items():
        print(f"\n{category}:")
        for ds in datasets:
            current = " (current)" if controller.current_dataset == ds['name'] else ""
            print(f"  {ds['index']}. {ds['name']}{current}")
    
    print("\nUse 'select <number>' to choose a dataset")

def process_command(cmd):
    cmd = cmd.strip()
    
    if not cmd:
        return True
        
    if cmd.lower() == 'list':
        list_available_datasets()
        return True
        
    elif cmd.lower() == 'help':
        print_help()
        return True
        
    elif cmd.lower() == 'exit':
        return False
        
    elif cmd.lower().startswith('select '):
        parts = cmd.split()
        if len(parts) == 2 and parts[1].isdigit():
            try:
                index = int(parts[1]) - 1  # Convert to 0-based
                flat_datasets = flatten_datasets(controller.available_datasets)
                
                if 0 <= index < len(flat_datasets):
                    dataset = flat_datasets[index]
                    # Create a proper dataset info dictionary
                    dataset_info = {
                        'name': dataset.get('name', 'Unknown'),
                        'path': dataset.get('path', ''),
                        'index': index + 1  # 1-based index for the server
                    }
                    if controller.select_dataset(dataset_info):
                        print(f"Selected dataset: {dataset['name']}")
                        return True
                    else:
                        print("Failed to select dataset. See error above.")
                else:
                    print(f"Invalid dataset number. Please use a number between 1 and {len(flat_datasets)}")
            except Exception as e:
                print(f"Error selecting dataset: {e}")
        else:
            print("Invalid select command. Use 'select <number>', where <number> is from the list command.")
        
        return True
    else:
        print("Unknown command. Type 'help' for available commands.")
        return True



def main():
    # Print welcome message
    print("\n" + "="*50)
    print("  NeuroSity Data Receiver")
    print("  Type 'help' for available commands")
    print("="*50 + "\n")
    
    # List available datasets
    list_available_datasets()
    
    # Command loop
    try:
        while controller.running:
            try:
                cmd = input("\nEnter command (help for options): ").strip()
                if not process_command(cmd):
                    break
            except KeyboardInterrupt:
                print("\nUse 'exit' to quit")
            except Exception as e:
                print(f"Error: {e}")
    finally:
        print("\nShutting down...")
        controller.close()
        print("Goodbye!")
        sys.exit(0)

if __name__ == '__main__':
    main()