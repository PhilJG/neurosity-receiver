from flask import Flask, request, jsonify
from websocket import create_connection
import threading
import json
import time

app = Flask(__name__)
latest_data = {}

# WebSocket client function
def websocket_client():
    ws_url = "ws://localhost:3000"
    while True:
        try: 
            ws = create_connection(ws_url)
            print(f"Connected to WebSocket at {ws_url}")

            while True:
                try: 
                    data = ws.recv()
                    if data:
                        parsed_data = json.loads(data)
                        global latest_data
                        latest_data = parsed_data
                        print(f"Recieved data: {parsed_data}")
                except Exception as e:
                    print(f"Error recieving data: {e}")
                    break

        except Exception as e:
            print(f"WebSocket connection error {e}")
            print("Retrying in 5 seconds...")
            time.sleep(5)

# Start WebSocket client in a separate thread
ws_thread = threading.Thread(target=websocket_client, daemon=True)
ws_thread.start()
            

@app.route('/api/data', methods=['POST'])
def recieve_data():
    data = request.get_json()
    global latest_data
    latest_data = data

    return jsonify({"status": "success", "data": data})

@app.route('/api/data/latest', methods=['GET'])
def get_data():
    return jsonify(latest_data) if latest_data else jsonify({"message": "No data recieved yet"})

if __name__ == '__main__':
    app.run(debug=True, port=5000)