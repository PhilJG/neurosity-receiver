from flask import Flask, request, jsonify

app = Flask(__name__)

latest_data = {}

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
    app.run(debug=True)