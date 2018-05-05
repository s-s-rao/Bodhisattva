import rainmaker
from flask import Flask, json, render_template, request, make_response, jsonify

app = Flask(__name__)

@app.route('/', methods=['GET', 'POST'])
def index():
	return render_template('index.html')

@app.route('/send-info', methods=['POST'])
def info():
	data = request.json['b']
	prediction = rainmaker.predict(data, "img")
	return jsonify({'prediction': prediction})

if __name__ == '__main__':
	app.run(debug = True, host="0.0.0.0", port=80)