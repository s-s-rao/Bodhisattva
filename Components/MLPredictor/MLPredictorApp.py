import os
import math
import base64
import pickle
import codecs
import numpy as np
import pandas as pd
import logging.config
from io import BytesIO
from pathlib import Path
from PIL import Image, ImageFilter
from warnings import filterwarnings
# from sklearn.preprocessing import LabelEncoder
# from sklearn.neural_network import MLPClassifier
# from sklearn.model_selection import train_test_split
from flask import Flask, json, request, make_response, jsonify

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

meta = json.load(open("meta.json"))
logging.config.fileConfig(str(Path("./log.conf")))
logger = logging.getLogger("root")

app = Flask(__name__)

confidenceLevelMode = {
	"MLPClassifier": "predict_proba",
	"SVMClassifier": "decision_function",
	"KNNClassifier": "predict_proba",
	"DecisionTreeClassifier": "predict_proba",
	"KMeansClustering": None
}

model = None
baseModelName = None
imageSize = 8, 8		# TODO: read from loadModel request

def predictProbaFunction(data):
	global model
	classes = model.classes_
	
	res = model.predict(data)
	res = res.tolist()

	prob = model.predict_proba(data)
	prob = np.around(prob, 3)
	prob = prob.tolist()

	# print(res.tolist())
	probNew = []
	for i, pr in enumerate(prob):
		# print(pr.tolist())
		prNew = {}
		for j, p in enumerate(pr):
			prNew[str(classes[j])] = p	# TODO: hardcoding to string type because of json encoding errors
		tmp = {"prediction": str(res[i]), "confidenceLevels": prNew}
		probNew.append(tmp)

	return probNew

def decisionFunction(data):
	global model
	classes = model.classes_

	dfs = model.decision_function(data)

	res = []

	myfunc = lambda x: 1 / (1 + math.exp(-x))
	vfunc = np.vectorize(myfunc)

	for i, df in enumerate(dfs):
		arr = np.asarray(df)
		arr = vfunc(arr)
		prob = arr.tolist()
		s = sum(prob)
		pred = classes[prob.index(max(prob))]
		pr = {}
		for j, p in enumerate(prob):
			pr[str(classes[j])] = p/s	# TODO: hardcoding to string type because of json encoding errors
		tmp = {"prediction": str(pred), "confidenceLevels": pr}
		res.append(tmp)

	return res

def probabilityFalse(data):
	out = model.predict(data)
	
	res = []
	for i, r in enumerate(out):
		res.append({"prediction": r})
	
	return res

# TODO: works only for MNIST. Make it generic.
def getImageArrayFromBase64String(encodingString):
	global imageSize
	img = Image.open(BytesIO(base64.b64decode(encodingString)))
	img.thumbnail(imageSize, Image.BILINEAR)

	img = img.filter(ImageFilter.EDGE_ENHANCE_MORE)
	img = img.filter(ImageFilter.DETAIL)
	img = img.filter(ImageFilter.DETAIL)
	img = img.filter(ImageFilter.DETAIL)
	img = img.convert("P")

	arr = np.array(img)
	arr = arr.clip(0,16)
	myfunc = lambda t: 16 - t
	vfunc = np.vectorize(myfunc)
	arr = vfunc(arr)
	print(arr)
	arr = arr.flatten()

	return arr

@app.route('/')
def hello_world():
	return 'This is the MLPredictor'


@app.route('/loadmodel', methods=["POST"])
def loadModel():
	global model, baseModelName, confidenceLevelMode
	modelPicklePath = request.json["modelPicklePath"]
	baseModelName = request.json["baseModelName"]

	if baseModelName not in confidenceLevelMode.keys():
		return {"status": 404, "message": "base model does not exist"}

	with open(modelPicklePath, "rb") as pkl:
		model = pickle.load(pkl)
	
	logger.info("Saved model loaded successfully from {}.".format(modelPicklePath))

	res = {"status": 200, "message": "Loaded model successfully."}

	return jsonify(res)


@app.route('/predict', methods=["POST"])
def predict():
	data = request.json["data"]		# always a list (of lists or base64 strings)
	
	dataType = None
	if "dataType" in request.json.keys():
		dataType = request.json["dataType"]
	
	if model is None:
		return jsonify({"status": 404, "message": "please load model before predicting"})
	
	# if data is image, assume only one image for prediction
	if dataType == "img":
		newData = []
		for d in data:
			t = getImageArrayFromBase64String(d)
			newData.append(t)
		data = newData
	
	probabilityType = confidenceLevelMode[baseModelName]
	
	if probabilityType is None:
		results = probabilityFalse(data)
	elif probabilityType == "predict_proba":
		results = predictProbaFunction(data)
	elif probabilityType == "decision_function":
		results = decisionFunction(data)
	
	if results:
		res = {
			"status": 200,
			"message": "Prediction made successfully.",
			"results": results
		}
		logger.info("Prediction made successfully.")		
	else:
		res = {
			"status": 400,
			"message": "Prediction failed."
		}
		logger.info("Prediction failed.")
	
	return jsonify(res)

@app.route('/check_alive', methods=["POST"])
def checkalive():
    responseMessage={
        "status": "success"
    }
    return jsonify(responseMessage)

if __name__ == '__main__':
	app.run(debug=True, use_reloader=False, host='0.0.0.0', port=80)
