import os
import pandas as pd
import logging.config
from pathlib import Path
from warnings import filterwarnings
# from sklearn.preprocessing import LabelEncoder
from sklearn.model_selection import train_test_split
from flask import Flask, json, request, make_response, jsonify

from MultiLayerPerceptron import MultiLayerPerceptron
from SupportVectorMachine import SupportVectorMachine

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

meta = json.load(open("meta.json"))
logging.config.fileConfig(str(Path("./log.conf")))
logger = logging.getLogger("root")

app = Flask(__name__)

availableBasicModels = {
	"MLPClassifier": MultiLayerPerceptron,
	"SVMClassifier": SupportVectorMachine
}

myModel = None
picklePath = ""


def getDataPath(fileName):
	dataPath = "/storage/data/" + fileName
	return dataPath

@app.route('/prepare', methods=["POST"])
def prepare():
	global myModel, picklePath, availableBasicModels
	
	req = request.json
	
	basicModel = req["baseModelName"]
	picklePath = req["picklePath"]
	
	if basicModel not in availableBasicModels.keys():
		return jsonify({"status": 400, "message": "Invalid model name."})
	
	model = availableBasicModels[basicModel]
	
	# data = pd.read_csv("iris.data")
	# featureColumns = ["sepal_length","sepal_width","petal_length","petal_width"]
	# labelColumn = "class"
	# features = data[list(featureColumns)].values
	# labels = data[labelColumn].values

	# data = req["data"]
	# data = pd.DataFrame.from_dict(data)
	
	dataFileNameInVolume = req["dataFileNameInVolume"]
	dataPath = getDataPath(dataFileNameInVolume)
	featureColumns = [i["columnName"] for i in req["featureColumns"]]
	labelColumn = req["labelColumns"][0]["columnName"]
	columns = featureColumns[:]
	columns.append(labelColumn)
	data = pd.read_csv(dataPath, names=columns, header=None)
	features = data[featureColumns]
	labels = data[labelColumn].values
	hyperparameters = req["hyperparameters"]
	modelParameters = req["modelParameters"]
	trainTestSplit = req["trainTestSplit"]

	# le = LabelEncoder()
	# le.fit(labels)
	# newLabels = le.transform(labels)
	# myModel = model(features, newLabels)

	myModel = model(features, labels, hyperparameters, modelParameters, trainTestSplit)

	logger.info("Model prepared successfully.")

	res = {"status": 200, "message": "model preparation completed"}

	return jsonify(res)


@app.route('/train', methods=["POST"])
def train():
	global myModel, picklePath
	
	myModel.train()

	logger.info("Model trained successfully.")
	
	myModel.saveModelPickle(picklePath)

	logger.info("Model pickle file saved into volume as {}.".format(picklePath))
	
	res = {"status": 200, "message": "model training completed", "picklePath": picklePath}

	return jsonify(res)

@app.route('/accuracy', methods=["POST"])
def accuracy():
	global myModel
	
	acc = myModel.accuracy() * 100.0

	logger.info("Model accuracy fetched successfully. Accuracy is {}.".format(str(acc)))
	
	res = {"status": 200, "message": "model accuracy", "accuracy": acc}

	return jsonify(res)

@app.route('/check_alive', methods=["POST"])
def checkalive():
	responseMessage = {
		"status": "success"
	}
	return jsonify(responseMessage)

@app.route('/')
def hello_world():
	return 'This is an MLTrainer'

if __name__ == '__main__':
	app.run(debug=True, use_reloader=False, host='0.0.0.0', port=80)
