import os
import pymysql
import requests
from decimal import *
import logging.config
from pathlib import Path
from pprint import pformat
from hashlib import sha256
from warnings import filterwarnings
from flask import Flask, json, request, make_response, render_template, jsonify

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

meta = json.load(open("meta.json"))
filterwarnings('ignore', category = pymysql.Warning)
logging.config.fileConfig(str(Path("./log.conf")))
logger = logging.getLogger("root")

app = Flask(__name__)

databaseCursor = pymysql.connect(
    host=meta["CSPDatabaseIPAddress"],
    user=meta["CSPDatabaseUsername"],
    passwd=meta["CSPDatabasePassword"],
    port=3306,
    autocommit=True
).cursor(pymysql.cursors.DictCursor)
databaseCursor.execute("use {};".format(meta["CSPDatabaseName"]))

# global variables
IPAddresses = {}
failedComponents = {}

# ----------------------Support Functions------------------------------
def validateToken(token):
    # TODO: complete it. validates token, and returns error message if token is not valid
    if not token:
        responseMessage = {
            "status": "error",
            "message": "Token credentials incorrect"
        }
        response = app.response_class(
            response=json.dumps(responseMessage),
            status=200,
            mimetype='application/json'
        )
        return response

@app.route("/obtain-ip-addresses")
def obtainIPAddresses():
    # obtain and store the CloudController's IPAddress
    query = "select IPAddress from Components where ComponentName = 'CloudController';"
    databaseCursor.execute(query)
    ipAddress = databaseCursor.fetchone()["IPAddress"]
    
    IPAddresses["cloudController"] = {
        "IPAddress": ipAddress,
        "Port": meta["CloudControllerPort"]
    }
    IPAddresses["MLController"] = {
        "IPAddress": ipAddress,
        "Port": meta["MLControllerPort"]
    }
    logger.info("Obtained the IP Addresses of CloudController and MLController")
    return jsonify({'status': 'success'})

# -------------------Infrastructure Setup------------------------------
@app.route('/api/tenant-signup', methods=['POST'])
def tenantSignup():
    # forward request to CloudController
    resp = requests.post("http://{}:{}/register-tenant".format(
        IPAddresses["cloudController"]["IPAddress"], IPAddresses["cloudController"]["Port"]), json=request.json)
    logger.info("Forwarded signup request to CloudController")

    response = app.response_class(
        response=json.dumps(resp.json()),
        status=200,
        mimetype='application/json'
    )
    logger.info("Tenant {} signup successful".format(request.json["tenantName"]))
    return response

@app.route('/api/tenant-login', methods=['POST'])
def tenantLogin():
    # Recieve Tenant Name and Password
    # Forward them to CloudController for authentication and recieve the token
    # Return the token back to Tenant

    tenantEmailId, tenantPassword = request.json["tenantEmailId"], request.json["tenantPassword"]
    loginCredentials = {
        "tenantEmailId": tenantEmailId,
        "tenantPassword": tenantPassword
    }

    resp = requests.post("http://{}:{}/authenticate".format(
        IPAddresses["cloudController"]["IPAddress"], IPAddresses["cloudController"]["Port"]), json=loginCredentials)

    response = app.response_class(
        response=json.dumps(resp.json()),
        status=200,
        mimetype='application/json'
    )
    logger.info("Tenant {} login successful".format(loginCredentials["tenantEmailId"]))
    return response

@app.route('/api/create-webapp', methods=['POST'])
def createWebApp():
    token = request.json["token"]
    url = request.json["url"]

    # validate token
    validationMessage = validateToken(token)
    if validationMessage is not None:
        return validationMessage

    webAppDetails = {
        "url": url,
        "tenantId": token["tenantId"]
    }

    resp = requests.post("http://{}:{}/create-webapp-images".format(
        IPAddresses["cloudController"]["IPAddress"], IPAddresses["cloudController"]["Port"]), json=webAppDetails)

    response = app.response_class(
        response=json.dumps(resp.json()),
        status=200,
        mimetype='application/json'
    )
    logger.info("WebApp created for Tenant {}".format(token["tenantName"]))
    return response

@app.route('/api/deploy-webapp-component', methods=['POST'])
def deployWebAppComponent():
    token = request.json["token"]
    componentType = request.json["componentType"]
    numOfComponents = request.json["numOfComponents"]

    # validate token
    validationMessage = validateToken(token)
    if validationMessage is not None:
        return validationMessage

    deploymentDetails = {
        "tenantId": token["tenantId"],
        "componentType": componentType,
        "numOfComponents": numOfComponents
    }

    resp = requests.post("http://{}:{}/new-component".format(
        IPAddresses["cloudController"]["IPAddress"], IPAddresses["cloudController"]["Port"]), json=deploymentDetails)

    response = app.response_class(
        response=json.dumps(resp.json()),
        status=200,
        mimetype='application/json'
    )
    logger.info("WebApp created for Tenant {}".format(token["tenantName"]))
    return response

# ----------------------Machine Learning APIs--------------------------
@app.route('/api/fetch-models', methods=['POST'])
def fetchModels():
    token = request.json["token"]
    # validate token
    validationMessage = validateToken(token)
    if validationMessage is not None:
        return validationMessage

    modelDetails = {}
    # fetch Un-trained models
    query = "select ModelId, ModelName, Description from Models where Type = 'untrained';"
    databaseCursor.execute(query)
    modelDetails["untrained"] = databaseCursor.fetchall()
    
    # fetch TenantTrained models
    query = """
        select Models.ModelId as ModelId, Models.ModelName as ModelName, Models.Description as Description
        from Models, TenantTrainedModels
        where Models.ModelId = TenantTrainedModels.ModelId and TenantTrainedModels.TenantId = {};
    """.format(token["tenantId"])
    databaseCursor.execute(query)
    modelDetails["tenanttrained"] = databaseCursor.fetchall()

    # fetch PretrainedModels models
    query = "select ModelId, ModelName, Description from Models where Type = 'pretrained';"
    databaseCursor.execute(query)
    modelDetails["pretrained"] = databaseCursor.fetchall()

    responseMessage = {
        "status": "success",
        "modelDetails": modelDetails
    }
    response = app.response_class(
        response=json.dumps(responseMessage),
        status=200,
        mimetype='application/json'
    )
    logger.info("Model details for tenantId {} fetched".format(token["tenantId"]))
    return response

@app.route('/api/get-deployment-template', methods=['POST'])
def getDeploymentTemplate():
    # get deploymentTemplate.json of the untrained model from MLController and return the response to frontend

    token = request.json["token"]
    # validate token
    validationMessage = validateToken(token)
    if validationMessage is not None:
        return validationMessage

    deploymentCredentials = {
        "modelId": request.json["modelId"],
        "tenantId": token["tenantId"]
    }

    # get deploymentTemplate from MLController
    deploymentTemplate = requests.post("http://{}:{}/get-deployment-template".format(
        IPAddresses["MLController"]["IPAddress"], IPAddresses["MLController"]["Port"]), json=deploymentCredentials)

    responseMessage = {
         "status": "success",
         "deploymentTemplate": deploymentTemplate.json()
    }
    # response = app.response_class(
    #     response=json.dumps(responseMessage),
    #     status=200,
    #     mimetype='application/json'
    # )
    logger.info("Returned DeploymentTemplate successfully")
    return jsonify(responseMessage)

@app.route('/api/prepare-model', methods=['POST'])
def prepareModel():
    # receive tenant model options from frontend and pass it to MLController
    token = request.json["token"]
    
    # validate token
    validationMessage = validateToken(token)
    if validationMessage is not None:
        return validationMessage

    filledDeploymentTemplate = request.json["filledDeploymentTemplate"]
    deploymentOptions = {
        "deploymentTemplate": filledDeploymentTemplate,
        "tenantId": token["tenantId"]
    }

    # forward filled DeploymentTemplate to MLController
    resp = requests.post("http://{}:{}/prepare-model".format(
        IPAddresses["MLController"]["IPAddress"], IPAddresses["MLController"]["Port"]), json=deploymentOptions)

    # responseMessage = {
    #     "status": "success",
    #     "message": resp.json()
    # }
    # response = app.response_class(
    #     response=json.dumps(responseMessage),
    #     status=200,
    #     mimetype='application/json'
    # )
    return jsonify(resp.json())

@app.route('/api/train-model', methods=["POST"])
def trainModel():
	# start training the model
	# request: tenantId, modelId
    token = request.json["token"]

    # validate token
    validationMessage = validateToken(token)
    if validationMessage is not None:
        return validationMessage

    modelId = request.json["modelId"]
    trainData = {
        "modelId": modelId,
        "tenantId": token["tenantId"]
    }

    # forward trainData to MLController
    resp = requests.post("http://{}:{}/train-model".format(
        IPAddresses["MLController"]["IPAddress"], IPAddresses["MLController"]["Port"]), json=trainData)

    #TODO: Training progress display

    # responseMessage = {
    #     "status": "success",
    #     "message": resp.json()
    # }
    # response = app.response_class(
    #     response=json.dumps(responseMessage),
    #     status=200,
    #     mimetype='application/json'
    # )
    return jsonify(resp.json())

@app.route('/api/start-predictors', methods=["POST"])
def deployModel():
	# deploy prediction service for a trained model
    token = request.json["token"]

    # validate token
    validationMessage = validateToken(token)
    if validationMessage is not None:
        return validationMessage

    deployData = {
        "modelId": request.json["modelId"],
        "tenantId": token["tenantId"],
        "numPredictors": request.json["numPredictors"]
    }

    # forward deployData to MLController
    resp = requests.post(
        "http://{}:{}/start-predictors".format(
            IPAddresses["MLController"]["IPAddress"], IPAddresses["MLController"]["Port"]), json=deployData)

    # responseMessage = {
    #     "status": "success",
    #     "message": resp.json()
    # }
    # response = app.response_class(
    #     response=json.dumps(responseMessage),
    #     status=200,
    #     mimetype='application/json'
    # )
    return jsonify(resp.json())

@app.route('/api/get-health', methods=["POST"])
def getHealth():
    token = request.json["token"]

    # validate token
    validationMessage = validateToken(token)
    if validationMessage is not None:
        return validationMessage
    
    if token["tenantId"] in failedComponents:
        responseMessage = {
            "status": "failed",
            "message": failedComponents[token["tenantId"]]
        }
    else:
        responseMessage = {
            "status": "success"
        }
    
    response = app.response_class(
        response=json.dumps(responseMessage),
        status=200,
        mimetype='application/json'
    )
    return response

"""
@app.route('/api/predict', methods=["POST"])
def predict():
	# deploy prediction service for a trained model
	# request: tenantId, modelId

    token = request.json["token"]
    modelId = request.json["modelId"]
    data = request.json["data"]

    # validate token
    validationMessage = validateToken(token)
    if validationMessage is not None:
        return validationMessage

    predictionData = {
        "modelId": modelId,
        "tenantId": token["tenantId"],
        "data": data
    }

    # get MLController's IPAddress
    query = "select IPAddress from Components where ComponentName = 'MLController';"
    databaseCursor.execute(query)
    result = databaseCursor.fetchone()
    resp = requests.post("http://{}/predict".format(result["IPAddress"]), json=predictionData)

    responseMessage = {
        "status": "success",
        "message": resp.json()
    }
    response = app.response_class(
        response=json.dumps(responseMessage),
        status=200,
        mimetype='application/json'
    )
    return response

 """

# ----------------------Maintainance-----------------------------------
@app.route('/api/remove-component', methods=["POST"])
def removeComponent():
    # request CloudController to remove the component
    # TODO: implementation pending
    componentId = request.json["componentId"]
    pass

@app.route('/heartbeat-response', methods=["POST"])
def heartbeat():
    global failedComponents

    if request.json["status"] == "success":
        # reset the failedComponents variable
        failedComponents = {}
    else:
        # update failedComponents[tenantId] global variable.
        result = request.json["failedComponents"]
        for i in result:
            if i[0] not in failedComponents:
                failedComponents[i[0]] = []
            failedComponents[i[0]].append(i[1:])
        #TODO: how long should a reported Component stay in reported div
        logger.info("Failed Components: {}".format(pformat(failedComponents)))

    responseMessage = {
        "status": "success"
    }
    response = app.response_class(
        response=json.dumps(responseMessage),
        status=200,
        mimetype='application/json'
    )
    return response

@app.route('/check_alive')
def checkalive():
    responseMessage={
        "status": "success"
    }
    return jsonify(responseMessage)

#---------------------------Graphs-------------------------------------
@app.route('/api/webapp-clicks', methods=['POST'])
def webAppClicks():
    tenantId = request.json["tenantId"]

    query = """
        select SUM(Loads.AccessCount) as Clicks
        from Loads, Components
        where Components.ComponentId = Loads.ComponentId and Components.TenantId = {} and Components.Type = 'WebRole';
    """.format(tenantId)

    databaseCursor.execute(query)
    result = databaseCursor.fetchone()
    
    return jsonify({
        "status": "success",
        "message": float(result["Clicks"])
    })

@app.route('/api/active-users', methods=['POST'])
def activeUsers():
    tenantId = request.json["tenantId"]

    query = """
        select SUM(LoadValue) as ActiveUsers
        from Loads, Components
        where Components.ComponentId = Loads.ComponentId and Components.TenantId = {} and Components.Type = 'WebRole';
    """.format(tenantId)

    databaseCursor.execute(query)
    result = databaseCursor.fetchone()

    return jsonify({
        "status": "success",
        "message": float(result["ActiveUsers"])
    })

@app.route('/api/instances-active-time', methods=['POST'])  # activetime
def instancesActiveTime():
    tenantId = request.json["tenantId"]
    componentType = request.json["componentType"]

    query = """
        select Loads.ActiveTime as ActiveTime, Components.ComponentName as ComponentName 
        from Loads, Components
        where Components.ComponentId = Loads.ComponentId and Components.TenantId = {} and Components.Type = '{}';
    """.format(tenantId, componentType)

    databaseCursor.execute(query)
    result = databaseCursor.fetchall()

    return jsonify({
        "status": "success",
        "message": result
    })

@app.route('/api/instance-load', methods=['POST'])
def instanceLoadVal():
    tenantId = request.json["tenantId"]

    query = """
        select Loads.ComponentId as Instance, Loads.LoadValue as LoadValue
        from Loads, Components
        where Components.ComponentId = Loads.ComponentId and Components.TenantId = {} and Components.Type = 'WebRole';
    """.format(tenantId)

    databaseCursor.execute(query)
    results = databaseCursor.fetchall()

    return jsonify({
        "status": "success",
        "message": results
    })

@app.route('/api/total-predictions', methods=['POST'])
def totalPredictions():
    tenantId = request.json["tenantId"]

    query = """
        select SUM(Loads.AccessCount) as TotalPredictions
        from Loads, Components
        where Components.ComponentId = Loads.ComponentId and Components.TenantId = {} and Components.Type = 'MLPredictor';
    """.format(tenantId)

    databaseCursor.execute(query)
    result = databaseCursor.fetchone()

    return jsonify({
        "status": "success",
        "message": float(result["TotalPredictions"])
    })

@app.route('/api/pre-trained-models-by-tenant', methods=['POST'])
def pretrainedModelsByTenant():
    tenantId = request.json["tenantId"]

    query = """
        select Count(distinct Predictors.ModelId) as Total
        from PretrainedModels, Predictors
        where PretrainedModels.ModelId = Predictors.ModelId and Predictors.TenantId = {}
    """.format(tenantId)

    databaseCursor.execute(query)
    result = databaseCursor.fetchone()

    return jsonify({
        "status": "success",
        "message": result["Total"]
    })

@app.route('/api/tenant-trained-models-deployed', methods=['POST'])
def tenantTrainedModelsDeployed():
    tenantId = request.json["tenantId"]

    query = """
        select Count(distinct Predictors.ModelId) as Total
        from TenantTrainedModels, Predictors
        where TenantTrainedModels.TenantId={} and Predictors.ModelId = TenantTrainedModels.ModelId 
    """.format(tenantId)

    databaseCursor.execute(query)
    result = databaseCursor.fetchone()

    return jsonify({
        "status": "success",
        "message": result["Total"]
    })

@app.route('/api/get-docker-stats', methods=['POST'])
def getDockerStats():
    tenantId = request.json["tenantId"]
    componentType = request.json["componentType"]

    resp = requests.post("http://{}:{}/get-docker-stats".format(
        IPAddresses["cloudController"]["IPAddress"], IPAddresses["cloudController"]["Port"]), json={"tenantId": tenantId, "componentType": componentType})

    return jsonify(resp.json())

@app.route('/api/tenant-trained-models-not-deployed', methods=['POST'])
def tenantTrainedModelsNotDeployed():
    tenantId = request.json["tenantId"]

    query1 = """
        select Count(*) as Total
        from TenantTrainedModels
        where TenantTrainedModels.TenantId={}  
    """.format(tenantId)

    query2 = """
        select Count(distinct Predictors.ModelId) as Total
        from TenantTrainedModels, Predictors
        where TenantTrainedModels.TenantId={} and Predictors.ModelId = TenantTrainedModels.ModelId
    """.format(tenantId)

    databaseCursor.execute(query1)
    result1 = databaseCursor.fetchone()

    databaseCursor.execute(query2)
    result2 = databaseCursor.fetchone()

    return jsonify({
        "status": "success",
        "message": result1["Total"] - result2["Total"]
    })

@app.route('/api/predictor-instances', methods=['POST'])
def predictorInstances():
    tenantId, modelId = request.json["tenantId"], request.json["modelId"]

    query = """
        select Count(*) as PredictorInstance
        from Predictors
        where TenantId={} and ModelId={};
    """.format(tenantId, modelId)

    databaseCursor.execute(query)
    result = databaseCursor.fetchone()

    return jsonify({
        "status": "success",
        "message": result["PredictorInstance"]
    })

# ---------------------------UI----------------------------------------
@app.route('/landing-page')
def landingPage():
    return render_template('landing_page.html')

@app.route('/')
@app.route('/index')
@app.route('/dashboard')
def dashboard():
    return render_template('dashboard.html')

@app.route('/webapp-details')
def webappDetails():
    return render_template('webapp_details.html')

@app.route('/models-details')
def modelsDetails():
    return render_template('models_details.html')

@app.route('/predictors-details')
def predictorsDetails():
    return render_template('predictors_details.html')

@app.route('/webapp-builder-wizard')
def webappBuilderWizard():
    return render_template('webapp_builder_wizard.html')

@app.route('/model-builder-wizard')
def modelBuilderWizard():
    return render_template('model_builder_wizard.html')

# TODO: need to use POST to get modelId, to make calls to predictors of that model
@app.route('/make-predictions')
def makePredictions():
    return render_template('make_predictions.html')

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=meta["AppPort"])
