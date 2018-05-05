import os
import time
import copy
import pymysql
import requests
import subprocess
import jsonschema
import pandas as pd
import logging.config
from pathlib import Path
from pprint import pprint
from shutil import copyfile
from warnings import filterwarnings
from flask import Flask, json, request, make_response, jsonify

import MLDataIngestionController as DataLayer

currentPath = "./Components/MLController/"

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

meta = json.load(open(currentPath + "meta.json"))
logging.config.fileConfig(str(Path(currentPath + "log.conf")))
logger = logging.getLogger("root")

app = Flask(__name__)

# filterwarnings('ignore', category=pymysql.Warning)
databaseCursor = pymysql.connect(
	host=meta["CSPDatabaseIPAddress"],
	user=meta["CSPDatabaseUsername"],
	passwd=meta["CSPDatabasePassword"],
	port=3306,
	autocommit=True
).cursor(pymysql.cursors.DictCursor)
databaseCursor.execute("use {};".format(meta["CSPDatabaseName"]))

models = {}		# modelId: modelDetails
volumeHostPaths = {}	# tenantId: hostPath(with trailing "/")

deploymentTemplatesPath = currentPath + "DeploymentTemplates/"
pretrainedModelPicklesPath = currentPath + "PretrainedModelPickles/"

untrainedModelsDetails = {}
untrainedModelsDetailsPath = currentPath + "UntrainedModelsDetails.json"

pretrainedModelsDetails = {}
pretrainedModelsDetailsPath = currentPath + "PretrainedModelsDetails.json"

APIRequestSchemas = {}
APIRequestSchemasPath = currentPath + "APIRequestSchemas.json"


def loadAPIRequestSchemas():
	global APIRequestSchemas

	APIRequestSchemas = json.load(open(APIRequestSchemasPath))
	return

def updateUntrainedModelsDetailsInDatabase():
	global untrainedModelsDetails, models
	
	untrainedModelsDetails = json.load(open(untrainedModelsDetailsPath))
	
	"""
	query = 'select * from Models where Type="untrained";'
	databaseCursor.execute(query)
	untrainedModelsDetailsFromDatabase = databaseCursor.fetchall()

	
	if len(untrainedModelsDetailsFromDatabase) == len(untrainedModelsDetails):
		return
 	"""

	for i, model in enumerate(untrainedModelsDetails[:]):
		query = """
			insert into Models (ModelName, Description, Type)
			values ('{}', '{}', '{}')
		""".format(model["name"], model["description"], "untrained")
		databaseCursor.execute(query)

		modelId = databaseCursor.lastrowid
		untrainedModelsDetails[i]["modelId"] = modelId

		dt = json.load(open(deploymentTemplatesPath + model["deploymentTemplateFileName"]))
		dt["modelDetails"]["baseModelId"]["value"] = modelId

		if not modelId in models.keys():
			models[str(modelId)] = {
				"type": "untrained",
				"name": model["name"],
				"fullName": model["fullName"],
				"description": model["description"],
				"deploymentTemplate": dt
			}
	
	logger.info("Added ML untrained models to Models table.")

	return

def updatePretrainedModelsDetailsInDatabaseAndCSPVolume():
	global pretrainedModelsDetails, models
	
	pretrainedModelsDetails = json.load(open(pretrainedModelsDetailsPath))

	hostPath = getHostPath(1)
	if not os.path.exists(hostPath + "data"):
		os.mkdir(hostPath + "data")

	for i, model in enumerate(pretrainedModelsDetails[:]):
		# insert into Models
		query = """
			insert into Models (ModelName, Description, Type)
			values ('{}', '{}', '{}')
		""".format(model["name"], model["description"], "pretrained")
		databaseCursor.execute(query)

		modelId = databaseCursor.lastrowid
		pretrainedModelsDetails[i]["modelId"] = modelId

		# create hostPath
		hostPath = getHostPath(1)
		if not os.path.exists(hostPath + str(modelId)):
			os.mkdir(hostPath + str(modelId))

		# dump DT into container conf path
		dt = json.load(open(deploymentTemplatesPath + model["deploymentTemplateFileName"]))
		dt["modelDetails"]["baseModelId"]["value"] = modelId
		containerConfPath = hostPathToConfPath(hostPath, modelId)
		with open(containerConfPath, "w+") as f:
			json.dump(dt, f, indent=4)

		# insert into PretrainedModels
		query = """
		insert into PretrainedModels (ModelId, ContainerConfPath)
		values ({},'{}')
		;
		""".format(str(modelId), containerConfPath)
		databaseCursor.execute(query)

		# copy pickle to modelPicklePath (host)
		picklePath = pretrainedModelPicklesPath + model["pickleFileName"]
		picklePathInVolume = getModelPicklePathForController(1, modelId)
		copyfile(picklePath, picklePathInVolume)

		# create entry in models dict - leave trainers empty; status is "trained"
		if not modelId in models.keys():
			models[str(modelId)] = {
				"type": "pretrained",
				"tenantId": 1,
				"name": model["name"],
				"fullName": model["fullName"],
				"description": model["description"],
				"deploymentTemplate": parseDeploymentTemplate(dt),
				"trainers": None,
				"predictors": {},
				"status": "trained"
			}

	
	logger.info("Added ML pretrained models to Models table.")

	return

def doesModelBelongToTenant(modelId, tenantId):
	global models
	if str(modelId) not in models.keys():
		return False
	if "tenantId" not in models[str(modelId)].keys():
		return False
	if models[str(modelId)]["tenantId"] != tenantId:
		return False
	return True

def validateRequest(APIName, data, strictMode=True):
	global APIRequestSchemas, models

	schema = APIRequestSchemas[APIName]

	if strictMode:
		if schema["type"] == "object":
			schema["required"] = list(schema["properties"].keys())
		schema["additionalProperties"] = False

	try:
		jsonschema.validate(data, schema)
	except jsonschema.exceptions.ValidationError:
		return False

	if "tenantId" in data.keys():
		databaseCursor.execute("select TenantId from Tenants;")
		tenantIds = databaseCursor.fetchall()
		tenantIds = [i["TenantId"] for i in tenantIds]
		if data["tenantId"] not in tenantIds:
			return False

	if "modelId" in data.keys():
		"""
		databaseCursor.execute("select ModelId from Models;".format(tenantId))
		modelIds = databaseCursor.fetchall()
		modelIds = [i["ModelId"] for i in modelIds]
		if data["modelId"] not in modelIds:
			return False
		"""
		if str(data["modelId"]) not in models.keys():
			return False

	return True

def findFreeSubnetSeries(tenantId):
	databaseCursor.execute("select IPAddress from Components where TenantId={};".format(str(tenantId)))
	addresses = databaseCursor.fetchall()
	used = [int(a["IPAddress"].split(".")[2]) for a in addresses]
	used.extend([1, 2, 3])
	subnets = set(used)
	subnets = list(subnets)
	subnets.sort()
	new = 0
	for i in range(len(subnets) - 3):
		j = i + 3
		diff = subnets[j] - subnets[j-1]
		if diff != 1:
			new = subnets[j] - 1
			break
	if new == 0:
		new = subnets[-1] + 1

	return new

def getHostPath(tenantId):
	if not tenantId in volumeHostPaths.keys():
		databaseCursor.execute("select HostPath from Volumes where TenantId={};".format(tenantId))
		# ASSUMING THAT EACH TENANT HAS ONLY ONE VOLUME ASSOCIATED WITH THEM
		hostPath = databaseCursor.fetchone()["HostPath"]
		if not hostPath[-1] == "/":
			hostPath += "/"
		volumeHostPaths[tenantId] = hostPath

	return volumeHostPaths[tenantId]

def hostPathToConfPath(hostPath, modelId):
	confPath = hostPath + str(modelId) + "/conf.json"
	return confPath

def getModelPicklePathForController(tenantId, modelId):
	modelPicklePath = getHostPath(tenantId) + str(modelId) + "/savedModel.pkl"
	return modelPicklePath

def getModelPicklePathForContainer(modelId):
	modelPicklePath = "/storage/" + str(modelId) + "/savedModel.pkl"
	return modelPicklePath

def parseDeploymentTemplate(old):
	# TODO: implement ERROR CHECKING and VALIDATION of deploymentTemplate (old)
	new = {}

	# modelDetails
	new["modelName"] = old["modelDetails"]["modelName"]["value"]
	new["modelDescription"] = old["modelDetails"]["modelDescription"]["value"]
	new["baseModelName"] = old["modelDetails"]["baseModelName"]["value"]
	new["baseModelId"] = old["modelDetails"]["baseModelId"]["value"]

	# trainingDataDetails
	new["dataSourceType"] = old["trainingDataDetails"]["dataSourceType"]["value"]
	if new["dataSourceType"] == "URL":
		new["dataSource"] = old["trainingDataDetails"]["dataSourceURL"]["value"]
	elif new["dataSourceType"] == "Existing":
		new["dataSource"] = old["trainingDataDetails"]["dataSourceExisting"]["value"]
	new["trainTestSplit"] = old["trainingDataDetails"]["trainTestSplit"]["value"] / 100.0

	featureColumns = []
	labelColumns = []
	for column in old["trainingDataDetails"]["dataSchema"]["value"]:
		c = column["value"]
		if "ignoreColumn" in c.keys() and c["ignoreColumn"]["value"]:
			continue										# ignore column if ignoreColumn set to true
		cc = {}
		cc["columnName"] = c["columnName"]["value"]
		cc["dataType"] = c["dataType"]["value"]
		if "isLabelColumn" in c.keys() and c["isLabelColumn"]["value"]:
			labelColumns.append(cc)
		else:
			featureColumns.append(cc)
	new["featureColumns"] = featureColumns
	new["labelColumns"] = labelColumns
	
	# hyperparameters
	h = {}
	for hp in old["hyperparameters"]["value"]:
		if hp["value"] == None:
			continue										# ignore hyperparameter if set to null (None)
		if "defaultValue" in hp.keys() and hp["value"] == hp["defaultValue"]:
			continue										# ignore hyperparameter if same as default value, as the sklearn model will plug in the default value to build the model
		hname = hp["hyperparameterNameDev"]
		h[hname] = hp["value"]
	new["hyperparameters"] = h

	# modelParameters
	m = {}
	for mp in old["modelParameters"]["value"]:
		if "useDefault" in mp.keys() and mp["useDefault"]:
			continue										# ignore model parameter if set to default
		if mp["value"] == None:
			continue										# ignore model parameter if value not set
		mname = mp["modelParameterNameDev"]
		m[mname] = mp["value"]
	new["modelParameters"] = m

	# trainingDeploymentParameters
	new["parallelizationMethod"] = old["trainingDeploymentParameters"]["parallelizationMethod"]["value"]

	# add more plugging in here when more options in deploymentTemplate

	logger.info("Parsed the deployment template for {}.".format(new["modelName"]))
	
	return new

def getMLTrainerProfiles(deploymentTemplate, tenantId, modelPicklePath):
	dt = deploymentTemplate
	if not dt["parallelizationMethod"] == "none":		# TODO: change when parallelization method(s) implemented 
		return False
	
	hostPath = getHostPath(tenantId)

	# get dataFileNameInVolume
	dataFileNameInVolume = dt["dataSource"]
	if dt["dataSourceType"] == "URL":
		resp = DataLayer.saveDataToVolume(dt["dataSource"], hostPath)
		if resp["status"] != 200:
			return False
		dataFileNameInVolume = resp["fileName"]
	
	logger.info("Downloaded file {} into tenant{}'s volume.".format(dataFileNameInVolume, str(tenantId)))

	""" 
	# send request to DataLayer and get data as Pandas dataframe
	data = DataLayer.getData(dt["dataSource"])
	 """

	profiles = {}

	# TODO: change this for training parallelization methods (HTaaS later) (no parallelization for now)
	profiles[0] = {
		"baseModelName": dt["baseModelName"],
		"baseModelId": dt["baseModelId"],
		"picklePath": modelPicklePath,				# TODO: pickle path for model should be handled by MLController, not MLTrainer (in distributed ML). For now, as there is only one MLTrainer instance, it can write the model to the pickle path directly. But later in distributed ML, individual models should be given back to MLController (or an MLTrainingController microservice), which will do some sort of consolidation of all the models and save a single model in the pickle path
		"dataFileNameInVolume": dataFileNameInVolume,
		"featureColumns": dt["featureColumns"],
		"labelColumns": dt["labelColumns"],
		"hyperparameters": dt["hyperparameters"],
		"modelParameters": dt["modelParameters"],
		"trainTestSplit": dt["trainTestSplit"]
	}

	logger.info("Created MLTrainer profiles for tenant{}'s model {}.".format(str(tenantId), dt["baseModelName"]))

	return profiles


""" 
@app.route('/retrieve-tenant-model-details', methods=["POST"])
def retrieveTenantModelDetails():
	tenantId = request.json["tenantId"]

	databaseCursor.execute("select * from Models where TenantId={};".format(tenantId))
	modelDetails = databaseCursor.fetchall()

	hostPath = getHostPath(tenantId)

	confDetails = []
	for model in modelDetails:
		confPath = hostPathToConfPath(hostPath, model["modelId"])
		with open(confPath, "r") as f:
			confDetail = json.load(f)
			confDetails.append(confDetail)

	res = zip(modelDetails, confDetails)

	print("RETRIEVE TENANT MODEL DETAILS: ")
	print(res)
	return jsonify(res)


@app.route('/retrieve-pretrained-model-details', methods=["GET"])
def retrievePretrainedModelDetails():
	databaseCursor.execute("select * from Models where TenantId=0 and Type=3;")
	modelDetails = databaseCursor.fetchall()

	hostPath = getHostPath(0)

	confDetails = []
	for model in modelDetails:
		confPath = hostPathToConfPath(hostPath, model["modelId"])
		with open(confPath, "r") as f:
			confDetail = json.load(f)
			confDetails.append(confDetail)

	res = zip(modelDetails, confDetails)

	print("RETRIEVE TENANT MODEL DETAILS: ")
	print(res)
	return jsonify(res)
 """


@app.route('/get-deployment-template', methods=["POST"])
def getDeploymentTemplate():
	global models

	if not validateRequest("getDeploymentTemplate", request.json):
		res = {"status": 400, "message": "Bad request."}
		return jsonify(res)

	modelId = request.json["modelId"]
	tenantId = request.json["tenantId"]

	"""
	if "tenantId" in models[str(modelId)].keys():
		if not doesModelBelongToTenant(modelId, 1):
			if not doesModelBelongToTenant(modelId, tenantId):
				res = {"status": 400, "message": "Model does not belong to tenant."}
				return jsonify(res)
	"""
	
	if "tenantId" in models[str(modelId)].keys():
		res = {"status": 400, "message": "Deployment templates of only untrained models can be fetched."}
		return jsonify(res)

	# query database and get model name and fetch corresponding DT
	# databaseCursor.execute("select ModelName from Models where ModelId={};".format(modelId))
	# modelName = databaseCursor.fetchone()["ModelName"]
	# dt = json.load(open(deploymentTemplatesPath + "MLPClassifier.json"))
	# dt = json.load(open(deploymentTemplatesPath + modelName + ".json"))

	# pprint(models.keys())

	# pprint(models)

	dt = models[str(modelId)]["deploymentTemplate"]

	# retrieve data files names from tenant's volume
	hostPath = getHostPath(tenantId)
	dataFolderPath = hostPath + "data/"
	dataFiles = os.listdir(dataFolderPath)	# returns only the file/folder names in the directory (non-recursive)

	# plug in the retrieved file names into the DT before returning
	dt["trainingDataDetails"]["dataSourceExisting"]["options"] = dataFiles

	logger.info("Plugged in datafile names from Volume into Deployment Template for {} for tenant {}.".format(dt["modelDetails"]["baseModelName"]["value"], str(tenantId)))

	res = {
		"status": 200,
		"message": "Deployment template fetched successfully.",
		"deploymentTemplate": dt
	}
	return jsonify(res)


@app.route('/prepare-model', methods=["POST"])
def prepareModel():
	global models

	if not validateRequest("prepareModel", request.json):
		res = {"status": 400, "message": "Bad request."}
		return jsonify(res)

	tenantId = request.json["tenantId"]
	deploymentTemplate = request.json["deploymentTemplate"]

	if tenantId == 1:
		modelType = "pretrained"
	else:
		modelType = "tenanttrained"

	parsedDeploymentTemplate = parseDeploymentTemplate(deploymentTemplate)

	modelName = parsedDeploymentTemplate["modelName"]
	modelDescription = parsedDeploymentTemplate["modelDescription"]

	query = """
	insert into Models (ModelName, Description, Type)
	values ('{}','{}','{}')
	;
	""".format(modelName, modelDescription, modelType)
	databaseCursor.execute(query)

	modelId = databaseCursor.lastrowid

	hostPath = getHostPath(tenantId)

	# create modelId directory in volume
	if not os.path.exists(hostPath + str(modelId)):
		os.mkdir(hostPath + str(modelId))

	containerConfPath = hostPathToConfPath(hostPath, modelId)
	with open(containerConfPath, "w+") as f:
		json.dump(deploymentTemplate, f, indent=4)

	if modelType == "pretrained":
		query = """
		insert into PretrainedModels (ModelId, ContainerConfPath)
		values ({},'{}')
		;
		""".format(str(modelId), containerConfPath)
		databaseCursor.execute(query)

	elif modelType == "tenanttrained":
		query = """
		insert into TenantTrainedModels (ModelId, TenantId, ContainerConfPath)
		values ({},{},'{}')
		;
		""".format(str(modelId), str(tenantId), containerConfPath)
		databaseCursor.execute(query)

	logger.info("Added new model {} with modelId {} to the correpsonding Models tables.".format(modelName, str(modelId)))

	logger.info("Created directory for model {} in the tenant{}'s volume.".format(str(modelId), str(tenantId)))

	modelPicklePath = getModelPicklePathForContainer(modelId)

	if not modelId in models.keys():
		models[str(modelId)] = {
			"type": "tenanttrained",
			"tenantId": tenantId,
			"deploymentTemplate": parsedDeploymentTemplate,
			"trainers": {},
			"predictors": {},
			"status": "created"		# will change to "prepared", "training", "training-interrupted", "partially-trained", "trained", "predicting", "not-predicting"
		}
	else:
		# TODO: allow retraining of an already trained model? IF SO, IMPLEMENT IT !!! Keep in mind - if retraining is allowed, MLTrainer instances cannot be stopped after model training is completed, as the existing trained models might have to be used to further train the model (for more epochs maybe)
		pass
	
	# save details of the MLTrainer(s) container so that it can be stopped and removed later
	
	MLTrainerProfiles = {}		# MLTrainerId : MLTrainerProfile
	respTemp = getMLTrainerProfiles(parsedDeploymentTemplate, tenantId, modelPicklePath)
	if not respTemp:
		res = {"status": 400, "message": "Model preparation failed."}
		return jsonify(res)
	MLTrainerProfiles = respTemp

	# start MLTrainerApp containers

	subnetSeries = findFreeSubnetSeries(tenantId)
	responses = {}		# MLTrainerId : response 
	for MLTrainerId, MLTrainerProfile in MLTrainerProfiles.items():	# TODO: depends on parallelization method applied

		# TODO: PARALLELIZE THIS STEP - use threading to call MLTrainer containers all at once (or in batches)
		# TODO: take care of writing data to the "models" variable, as it might be tricky
			# acquire lock before writing to "models"

		# TODO: nomenclature of component name
		# MLTrainerComponentName = "MLTrainer" + str(tenantId) + "_" + str(MLTrainerId + 1)
		MLTrainerComponentName = "MLTrainer" + str(modelId) + "_" + str(MLTrainerId + 1)
		MLTrainerIPAddress = "10." + str(tenantId) + "." + str(subnetSeries) + "." + str(MLTrainerId + 1)

		# MLTrainerPort = {
		# 	"AppPort": 80,
		# 	"ContainerPort": 9007
		# }
		# cmd = """docker run --network=RainMakerNetwork --ip={} --name={} -d -v volume{}:/storage -p {}:{} flask-{}""".format(
		# 	MLTrainerIPAddress, MLTrainerComponentName, str(tenantId), MLTrainerPort["ContainerPort"], MLTrainerPort["AppPort"], MLTrainerComponentName.lower())
		# containerId = subprocess.getoutput(cmd).split("\n")[-1]

		cmd = """docker run --network=RainMakerNetwork --ip={} --name={} -d -v volume{}:/storage flask-{}""".format(
			MLTrainerIPAddress, MLTrainerComponentName, str(tenantId), "mltrainer")
		containerId = subprocess.getoutput(cmd).split("\n")[-1]

		logger.info("Started running {} container at {} for tenant{}.".format(MLTrainerComponentName, MLTrainerIPAddress, str(tenantId)))

		# add new MLTrainer container to Components table in CSPDb
		query = """
		insert into Components (ComponentId, ComponentName, IPAddress, TenantId, Type)
		values ('{}','{}','{}',{},'{}')
		""".format(containerId, MLTrainerComponentName, MLTrainerIPAddress, tenantId, "MLTrainer")
		databaseCursor.execute(query)

		logger.info("Added {} of tenant{} to Components table in CSPDb.".format(MLTrainerComponentName, str(tenantId)))

		MLTrainerDetails = {
			"MLTrainerComponentName": MLTrainerComponentName,
			"MLTrainerIPAddress": MLTrainerIPAddress,
			"containerId": containerId,
			"MLTrainerProfile": MLTrainerProfile
		}

		# TODO: acquire lock on "models"
		models[str(modelId)]["trainers"][str(MLTrainerId)] = MLTrainerDetails
		# TODO: release lock

		# wait for MLTrainer container to start listening to requests - TODO: IS THIS REQUIRED? DOES THE "docker run" COMMAND RETURN containerId ONLY AFTER SUCCESSFULLY SPAWNING THE CONTAINER?
		while True:
			cmd = """ping -c 1 {}""".format(MLTrainerIPAddress)
			pingResponse = os.system(cmd)
			if pingResponse == 0:
				break
			time.sleep(1)		# sleeps the thread, not process
		time.sleep(5)		# to overcome "max retries exceeded" error

		resp = requests.post("http://" + MLTrainerIPAddress + "/prepare", json=MLTrainerProfile)
		response = resp.json()
		# TODO: acquire lock on "responses"
		responses[MLTrainerId] = response
		# TODO: release lock

		logger.info("Prepared the model within the {} container for tenant{}.".format(MLTrainerComponentName, str(tenantId)))

	models[str(modelId)]["status"] = "prepared"	

	res = {
		"status": 200,
		"message": ""
	}

	for MLTrainerId, resp in responses.items():
		if not resp["status"] == 200:
			res["status"] = 400
			res["message"] += str(MLTrainerId) + ", "
	if res["status"] == 200:
		res["message"] = "Model preparation successful."
		res["modelId"] = modelId
	else:
		res["message"] = "Model preparation failed. " + res["message"][:-2] + " MLTrainers failed."
	
	return jsonify(res)


@app.route('/train-model', methods=["POST"])
def trainModel():
	global models

	if not validateRequest("trainModel", request.json):
		res = {"status": 400, "message": "Bad request."}
		return jsonify(res)

	tenantId = request.json["tenantId"]
	modelId = request.json["modelId"]

	if not doesModelBelongToTenant(modelId, tenantId):
		res = {"status": 400, "message": "Model does not belong to tenant."}
		return jsonify(res)

	if not models[str(modelId)]["status"] == "prepared":
		res = {"status": 400, "message": "Model not prepared for training."}
		return jsonify(res)

	trainers = models[str(modelId)]["trainers"]

	if len(trainers.keys()) == 0:
		res = {"status": 400, "message": "Model not prepared."}
		return jsonify(res)

	responses = {}		# MLTrainerId : response
	bestAccuracy = 0.0
	bestMLTrainer = None

	for MLTrainerId, MLTrainerDetails in trainers.items():	# TODO: depends on parallelization method applied

		# TODO: PARALLELIZE THIS STEP - use threading to call MLTrainer containers all at once (or in batches)

		MLTrainerIPAddress = MLTrainerDetails["MLTrainerIPAddress"]
		MLTrainerContainerId = MLTrainerDetails["containerId"]
		MLTrainerComponentName = MLTrainerDetails["MLTrainerComponentName"]

		resp = requests.post("http://" + MLTrainerIPAddress + "/train", json={})
		models[str(modelId)]["status"] = "training"
		response = resp.json()
		# TODO: acquire lock on "responses"
		responses[MLTrainerId] = response
		# TODO: release lock

		logger.info("Finished training the model on the {} container.".format(MLTrainerComponentName))

		time.sleep(3)		# to overcome "max retries exceeded" error

		# get accuracy of model
		resp = requests.post("http://" + MLTrainerIPAddress + "/accuracy", json={})
		response = resp.json()

		responses[MLTrainerId]["accuracy"] = response["accuracy"]

		logger.info("Received accuracy from the model trained on the {} container. Accuracy is {}".format(MLTrainerComponentName, str(response["accuracy"])))

		forceRemoveContainer = False
		# stop and remove MLTrainer container
		cmd = """docker stop {}""".format(MLTrainerContainerId)
		containerId = subprocess.getoutput(cmd)
		if containerId == MLTrainerContainerId:
			logger.info("Stopped {} container.".format(MLTrainerComponentName))
		else:
			logger.info("Unable to stop {} container.".format(MLTrainerComponentName))
			forceRemoveContainer = True

		forceRemoveContainerOption = ""
		if forceRemoveContainer:
			forceRemoveContainerOption = "--force"
		cmd = """docker rm {} {}""".format(forceRemoveContainerOption, MLTrainerContainerId)
		containerId = subprocess.getoutput(cmd)
		if containerId == MLTrainerContainerId:
			logger.info("Removed {} container.".format(MLTrainerComponentName))
		else:
			logger.info("Unable to remove {} container.".format(MLTrainerComponentName))

		# remove MLTrainer container from Components table in CSPDb
		query = """
		delete from Components
		where ComponentId = '{}'
		""".format(MLTrainerContainerId)
		databaseCursor.execute(query)

		logger.info("Deleted {} component from the Components table.".format(MLTrainerComponentName))

	models[str(modelId)]["trainers"] = {}
	models[str(modelId)]["status"] = "trained"

	res = {
		"status": 200,
		"message": ""
	}

	# TODO: how to combine accuracy from all trainers?
	# for now, accuracy = max accuracy

	accuracy = 0.0
	maxAccuracyTrainerId = 0

	for MLTrainerId, resp in responses.items():
		if not resp["status"] == 200:
			res["status"] = 400
			res["message"] += str(MLTrainerId) + ", "
		else:
			if resp["accuracy"] > accuracy:
				accuracy = resp["accuracy"]
				maxAccuracyTrainerId = MLTrainerId
	if res["status"] == 200:
		res["message"] = "Training successful. MLTrainer " + str(maxAccuracyTrainerId) + " trained the most accurate model."
		res["accuracy"] = accuracy
	else:
		res["message"] = "Training failed. " + res["message"][:-2] + " MLTrainers failed."
	
	return jsonify(res)


@app.route('/stop-model-training', methods=["POST"])
def stopModelTraining():
	# stop training the model
	# input: tenantId, modelId
	# output: trainingStatusMessage

	if not validateRequest("stopModelTraining", request.json):
		res = {"status": 400, "message": "Bad request."}
		return jsonify(res)

	tenantId = request.json["tenantId"]
	modelId = request.json["modelId"]

	if not doesModelBelongToTenant(modelId, tenantId):
		res = {"status": 400, "message": "Model does not belong to tenant."}
		return jsonify(res)

	if not models[str(modelId)]["status"] == "training":
		res = {"status": 400, "message": "Model not being trained at the moment."}
		return jsonify(res)

	trainers = models[str(modelId)]["trainers"]

	if len(trainers.keys()) == 0:
		res = {"status": 400, "message": "Model not prepared."}
		return jsonify(res)

	for MLTrainerId, MLTrainerDetails in sorted(list(trainers.items()), key=lambda x: int(x[0]), reverse=True):	# TODO: depends on parallelization method applied

		# TODO: PARALLELIZE THIS STEP - use threading to call MLTrainer containers all at once (or in batches)

		MLTrainerContainerId = MLTrainerDetails["containerId"]
		MLTrainerComponentName = MLTrainerDetails["MLTrainerComponentName"]

		forceRemoveContainer = False
		# stop and remove MLTrainer container
		cmd = """docker stop {}""".format(MLTrainerContainerId)
		containerId = subprocess.getoutput(cmd)
		if containerId == MLTrainerContainerId:
			logger.info("Stopped {} container.".format(MLTrainerComponentName))
		else:
			logger.info("Unable to stop {} container.".format(MLTrainerComponentName))
			forceRemoveContainer = True

		forceRemoveContainerOption = ""
		if forceRemoveContainer:
			forceRemoveContainerOption = "--force"
		cmd = """docker rm {} {}""".format(forceRemoveContainerOption, MLTrainerContainerId)
		containerId = subprocess.getoutput(cmd)
		if containerId == MLTrainerContainerId:
			logger.info("Removed {} container.".format(MLTrainerComponentName))
		else:
			logger.info("Unable to remove {} container.".format(MLTrainerComponentName))

		# remove MLTrainer container from Components table in CSPDb
		query = """
		delete from Components
		where ComponentId = '{}'
		""".format(MLTrainerContainerId)
		databaseCursor.execute(query)

		logger.info("Deleted {} component from the Components table.".format(MLTrainerComponentName))

	models[str(modelId)]["trainers"] = {}
	models[str(modelId)]["status"] = "training-interrupted"

	res = {"status": 200, "message": "Model training stopped successfully."}

	return jsonify(res)


# TODO:
@app.route('/get-training-progress', methods=["POST"])
def getTrainingProgress():
	# get the current training progress report (parameters, resources used, etc)
	# input: tenantId, modelId
	# output: progressReport (json)

	modelId = request.json["modelId"]
	tenantId = request.json["tenantId"]

	if not validateRequest("getTrainingProgress", request.json):
		res = {"status": 400, "message": "Bad request."}
		return jsonify(res)

	if not doesModelBelongToTenant(modelId, tenantId):
		res = {"status": 400, "message": "Model does not belong to tenant."}
		return jsonify(res)

	# TODO: streaming vs long-polling -> at the moment, long-polling seems like a better idea, but too many API requests. THAT'S COMPLETELY FINE FOR A COLLEGE PROJECT

	pass


@app.route('/start-predictors', methods=["POST"])
def startPredictors():
	# start MLPredictor instances - scaling up (out)
	# input: tenantId, modelId, numPredictors
	# output: successMessage

	global models

	if not validateRequest("startPredictors", request.json):
		res = {"status": 400, "message": "Bad request."}
		return jsonify(res)

	tenantId = request.json["tenantId"]
	modelId = request.json["modelId"]
	numPredictors = request.json["numPredictors"]

	if not doesModelBelongToTenant(modelId, tenantId):
		if doesModelBelongToTenant(modelId, 1):
			# copy pickle from CSP volume to tenant's volume
			modelPicklePathInCSPVolume = getModelPicklePathForController(1, modelId)
			modelPicklePathInTenantVolume = getModelPicklePathForController(tenantId, modelId)
			hostPath = getHostPath(tenantId)
			if not os.path.exists(hostPath + str(modelId)):
				os.mkdir(hostPath + str(modelId))
			copyfile(modelPicklePathInCSPVolume, modelPicklePathInTenantVolume)
			logger.info("Copied pretrained model{}'s pickle to tenant{}'s volume.".format(str(modelId), str(tenantId)))
		else:
			res = {"status": 400, "message": "Model does not belong to tenant."}
			return jsonify(res)

	# checking if model has been trained before deploying predictors
	if models[str(modelId)]["status"] not in ["trained", "predicting", "not-predicting"]:
		res = {"status": 400, "message": "Untrained model cannot be deployed for prediction."}
		return jsonify(res)
	"""
	if not os.path.exists(getModelPicklePathForController(tenantId, modelId)):
		logger.info("Cannot create predictors as trained model does not exist at path {}".format(getModelPicklePathForController(tenantId, modelId)))
		res = {"status": 400, "message": "Untrained model cannot be deployed for prediction."}
		return jsonify(res)
	"""

	modelPicklePath = getModelPicklePathForContainer(modelId)
	MLPredictorProfile = {
		"modelPicklePath": modelPicklePath,
		"baseModelName": models[str(modelId)]["deploymentTemplate"]["baseModelName"]
	}

	if not str(tenantId) in models[str(modelId)]["predictors"].keys():
		models[str(modelId)]["predictors"][str(tenantId)] = []
	predictors = copy.deepcopy(models[str(modelId)]["predictors"][str(tenantId)])

	logger.info("----------------predictors for tenant{}'s model{} are {}".format(str(tenantId), str(modelId), str(list(predictors))))

	nextPredictorId = len(predictors)
	if nextPredictorId == 0:
		subnetSeries = findFreeSubnetSeries(tenantId)
	else:
		subnetSeries = int(predictors[0]["MLPredictorIPAddress"].split(".")[2])

	predictorIPAddresses = []
	responses = {}		# MLPredictorId : response 
	for MLPredictorId in range(nextPredictorId, nextPredictorId + numPredictors):	# TODO: depends on parallelization method applied

		# TODO: PARALLELIZE THIS STEP - use threading to call MLTrainer containers all at once (or in batches)
		# TODO: take care of writing data to the "models" variable, as it might be tricky
			# acquire lock before writing to "models"

		# TODO: nomenclature of component name
		# MLPredictorComponentName = "MLPredictor" + str(tenantId) + "_" + str(MLPredictorId + 1)
		MLPredictorComponentName = "MLPredictor" + str(modelId) + "_" + str(tenantId) + "_" + str(MLPredictorId + 1)
		MLPredictorIPAddress = "10." + str(tenantId) + "." + str(subnetSeries) + "." + str(MLPredictorId + 1)

		cmd = """docker run --network=RainMakerNetwork --ip={} --name={} -d -v volume{}:/storage flask-{}""".format(
			MLPredictorIPAddress, MLPredictorComponentName, str(tenantId), "mlpredictor")
		containerId = subprocess.getoutput(cmd).split("\n")[-1]

		models[str(modelId)]["status"] = "predicting"

		logger.info("Started running {} container at {} for tenant{}.".format(MLPredictorComponentName, MLPredictorIPAddress, str(tenantId)))

		# add new MLPredictor container to Components table in CSPDb
		query = """
		insert into Components (ComponentId, ComponentName, IPAddress, TenantId, Type)
		values ('{}','{}','{}',{},'{}')
		""".format(containerId, MLPredictorComponentName, MLPredictorIPAddress, tenantId, "MLPredictor")
		databaseCursor.execute(query)

		logger.info("Added {} to Components table in CSPDb for tenant{}.".format(MLPredictorComponentName, str(tenantId)))

		# add new MLPredictor container to Loads table in CSPDb		
		query = """
		insert into Loads (ComponentId, LoadValue, ActiveTime)
		values ('{}',0,0)
		""".format(containerId)
		databaseCursor.execute(query)

		logger.info("Added an entry for {} in Loads table in CSPDb for tenant{}.".format(MLPredictorComponentName, str(tenantId)))

		# add entry in Predictors table in CSPDb
		query = """
		insert into Predictors (ComponentId, TenantId, ModelId)
		values ('{}',{},{})
		""".format(containerId, str(tenantId), str(modelId))
		databaseCursor.execute(query)

		logger.info("Added an entry for {} in Predictors table in CSPDb for tenant{}.".format(MLPredictorComponentName, str(tenantId)))

		MLPredictorDetails = {
			"MLPredictorComponentName": MLPredictorComponentName,
			"MLPredictorIPAddress": MLPredictorIPAddress,
			"containerId": containerId,
			"MLPredictorProfile": MLPredictorProfile
		}

		# TODO: acquire lock on "models"
		models[str(modelId)]["predictors"][str(tenantId)].append(MLPredictorDetails)
		# TODO: release lock

		# wait for MLPredictor container to start listening to requests - TODO: IS THIS REQUIRED? DOES THE "docker run" COMMAND RETURN containerId ONLY AFTER SUCCESSFULLY SPAWNING THE CONTAINER?
		while True:
			cmd = """ping -c 1 {}""".format(MLPredictorIPAddress)
			pingResponse = os.system(cmd)
			if pingResponse == 0:
				break
			time.sleep(1)		# sleeps the thread, not process
		time.sleep(5)		# to overcome "max retries exceeded" error

		resp = requests.post("http://" + MLPredictorIPAddress + "/loadmodel", json=MLPredictorProfile)
		response = resp.json()
		# TODO: acquire lock on "responses"
		responses[MLPredictorId] = response
		# TODO: release lock

		predictorIPAddresses.append(MLPredictorIPAddress)

		logger.info("Loaded the saved model on {} container for tenant{}.".format(MLPredictorComponentName, str(tenantId)))

	res = {
		"status": 200,
		"message": ""
	}

	for MLPredictorId, resp in responses.items():
		if not resp["status"] == 200:
			res["status"] = 400
			res["message"] += str(MLPredictorId) + ", "
	if res["status"] == 200:
		res["message"] = str(numPredictors) + " new MLPredictors have been successfully added to the prediction service."
		res["predictorIPAddresses"] = predictorIPAddresses
	else:
		res["message"] = "Predictors have failed to initialize. " + res["message"][:-2] + " MLPredictors failed."
	
	print("+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
	print("Started predictors. Model: ", str(modelId), ". Tenant: ", str(tenantId))
	pprint(models[str(modelId)]["predictors"])
	print("+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")

	return jsonify(res)


@app.route('/stop-predictors', methods=["POST"])
def stopPredictors():
	# completely stop the prediction service, ie, all the MLPredictors are stopped
	# input: tenantId, modelId, numPredictors
	# output: successMessage

	if not validateRequest("stopPredictors", request.json):
		res = {"status": 400, "message": "Bad request."}
		return jsonify(res)

	tenantId = request.json["tenantId"]
	modelId = request.json["modelId"]
	numPredictors = request.json["numPredictors"]

	if not doesModelBelongToTenant(modelId, tenantId):
		if not doesModelBelongToTenant(modelId, 1):
			res = {"status": 400, "message": "Model does not belong to tenant."}
			return jsonify(res)

	if str(tenantId) not in models[str(modelId)]["predictors"].keys():
		res = {"status": 400, "message": "There are no running predictors at the moment."}
		return jsonify(res)
	
	predictors = copy.deepcopy(models[str(modelId)]["predictors"][str(tenantId)])

	if len(predictors) == 0:
		res = {"status": 400, "message": "No predictors running."}
		return jsonify(res)

	"""
	if not models[str(modelId)]["status"] == "predicting":
		res = {"status": 400, "message": "There are no running predictors."}
		return jsonify(res)
	"""

	if numPredictors > len(predictors):
		numPredictors = len(predictors)
		logger.info("Tenant{} requested to remove more predictors than the actual number of running predictors for model{}. Hence, all predictors will be removed.".format(str(tenantId), str(modelId)))

	for MLPredictorDetails in list(reversed(predictors))[:numPredictors]:	# TODO: depends on parallelization method applied
		# TODO: PARALLELIZE THIS STEP - use threading to call MLPredictor containers all at once (or in batches)

		MLPredictorContainerId = MLPredictorDetails["containerId"]
		MLPredictorComponentName = MLPredictorDetails["MLPredictorComponentName"]

		forceRemoveContainer = False
		# stop and remove MLPredictor container
		cmd = """docker stop {}""".format(MLPredictorContainerId)
		containerId = subprocess.getoutput(cmd)
		if containerId == MLPredictorContainerId:
			logger.info("Stopped {} container.".format(MLPredictorComponentName))
		else:
			logger.info("Unable to stop {} container.".format(MLPredictorComponentName))
			forceRemoveContainer = True

		forceRemoveContainerOption = ""
		if forceRemoveContainer:
			forceRemoveContainerOption = "--force"
		cmd = """docker rm {} {}""".format(forceRemoveContainerOption, MLPredictorContainerId)
		containerId = subprocess.getoutput(cmd)
		if containerId == MLPredictorContainerId:
			logger.info("Removed {} container.".format(MLPredictorComponentName))
		else:
			logger.info("Unable to remove {} container.".format(MLPredictorComponentName))

		# remove MLPredictor entries from Loads table in CSPDb
		query = """
		delete from Loads
		where ComponentId = '{}'
		""".format(MLPredictorContainerId)
		databaseCursor.execute(query)

		logger.info("Deleted {} component from the Loads table.".format(MLPredictorComponentName))

		# remove MLPredictor entries from Components table in CSPDb
		query = """
		delete from Components
		where ComponentId = '{}'
		""".format(MLPredictorContainerId)
		databaseCursor.execute(query)

		logger.info("Deleted {} component from the Components table.".format(MLPredictorComponentName))

		# remove one entry from Predictors table
		query = """
		delete from Predictors
		where (PredictorId in ( select PredictorId from Predictors
								where TenantId={} and ModelId={}
								order by PredictorId desc limit 1))
		""".format(str(tenantId), str(modelId))
		databaseCursor.execute(query)

		models[str(modelId)]["predictors"][str(tenantId)].pop()

		logger.info("Deleted {} component from the predictors dict in the models dict.".format(MLPredictorComponentName))

	if len(models[str(modelId)]["predictors"].keys()) == 0:
		models[str(modelId)]["status"] = "not-predicting"

	res = {
		"status": 200,
		"message": str(numPredictors) + " MLPredictors have been successfully removed from the prediction service."
	}

	print("+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")
	print("Stopped predictors. Model: ", str(modelId), ". Tenant: ", str(tenantId))
	pprint(models[str(modelId)]["predictors"])
	print("+++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++++")

	return jsonify(res)


""" 
@app.route('/predict', methods=["POST"])
def predict():
	# make a prediction for given data
	# input: tenantId, modelId, data
	# output: predictionOutput

	tenantId = request.json["tenantId"]
	modelId = request.json["modelId"]
	data = request.json["data"]

	# call MLPredictor's 'predict' API and get output from it
	predictors = models[str(modelId)]["predictors"]

	MLPredictorDetails = predictors[0]

	MLPredictorIPAddress = MLPredictorDetails["MLPredictorIPAddress"]

	payload = {
		"data": data
	}

	resp = requests.post(MLPredictorIPAddress + "/predict", json=payload)
	response = resp.json()

	res = response

	return jsonify(res)
 """


@app.route('/')
def helloWorld():
	return 'This is the MLController'

if __name__ == '__main__':
	loadAPIRequestSchemas()
	updateUntrainedModelsDetailsInDatabase()
	updatePretrainedModelsDetailsInDatabaseAndCSPVolume()
	app.run(debug=True, use_reloader=False, host='0.0.0.0', port=meta["MLControllerPort"])
