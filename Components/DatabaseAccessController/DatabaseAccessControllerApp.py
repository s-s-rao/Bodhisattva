import json
from flask import Flask, jsonify

app = Flask(__name__)
meta = json.load(open("meta.json"))

@app.route('/')
def hello_world():
    return 'This is the DatabaseAccessControllerApp'

@app.route('/check_alive')
def checkalive():
    responseMessage={
        "status": "success"
    }
    return jsonify(responseMessage)
    
if __name__ == '__main__':
    app.run(debug=True,host='0.0.0.0', port=meta["AppPort"])
