import json
import time
import pymysql
import requests
import subprocess
import logging.config
from pathlib import Path
from pprint import pformat
from warnings import filterwarnings
from flask import Flask, request, jsonify

app = Flask(__name__)

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

meta = json.load(open("meta.json"))
filterwarnings('ignore', category=pymysql.Warning)
logging.config.fileConfig(str(Path("./log.conf")))
logger = logging.getLogger("root")

startTimes = {}

CSPDatabaseCursor = pymysql.connect(
    host=meta["CSPDatabaseIPAddress"],
    user=meta["CSPDatabaseUsername"],
    passwd=meta["CSPDatabasePassword"],
    port=3306,
    autocommit=True
).cursor(pymysql.cursors.DictCursor)
CSPDatabaseCursor.execute("use {};".format(meta["CSPDatabaseName"]))

@app.route('/request-instance', methods=["POST"])
def optimiseLoad():
    # obtain the IPAddress of the component with the least load
    # update the load, log the current time in startTimes variable.

    instanceOf, tenantId = request.json["componentType"], request.json["tenantId"]
    if instanceOf == "WebRole":
        query = """
            select Loads.ComponentId as ComponentId, Components.IPAddress as IPAddress
            from Loads, Components
            where Components.ComponentId = Loads.ComponentId and Components.tenantId = {} and Components.Type = '{}'
            order by Loads.LoadValue ASC
            limit 1;
        """.format(tenantId, instanceOf)
        CSPDatabaseCursor.execute(query)
        result = CSPDatabaseCursor.fetchone()
        query = """
            select IPAddress from Components where ComponentName = 'CloudController'
        """
        CSPDatabaseCursor.execute(query)
        result["HostIPAddress"] = CSPDatabaseCursor.fetchone()["IPAddress"]

        result["Port"] = requests.post("http://{}:{}/get-port".format(
            result["HostIPAddress"], meta["CloudControllerPort"]), json={"componentId": result["ComponentId"]}).json()

    elif instanceOf == "WorkerRole":
        query = """
            select Loads.ComponentId as ComponentId, Components.IPAddress as IPAddress
            from Loads, Components
            where Components.ComponentId = Loads.ComponentId and Components.tenantId = {} and Components.Type = '{}'
            order by Loads.LoadValue ASC
            limit 1;
        """.format(tenantId, instanceOf)
        CSPDatabaseCursor.execute(query)
        result = CSPDatabaseCursor.fetchone()
    
    elif instanceOf == "MLPredictor":
        query = """
            select Loads.ComponentId as ComponentId, Components.IPAddress as IPAddress, Components.ComponentName as ComponentName
            from Loads, Components, Predictors
            where Components.ComponentId = Loads.ComponentId and Predictors.ComponentId = Components.ComponentId and Predictors.ModelId = {} and Components.tenantId = {} and Components.Type = '{}'
            order by Loads.LoadValue ASC;
        """.format(request.json["modelId"], tenantId, instanceOf)
        CSPDatabaseCursor.execute(query)
        result = CSPDatabaseCursor.fetchone()

    if result is None:
        resp = {"status": 400, "message": "No instances available."}
        return jsonify(resp)

    query = """
        update Loads
        set LoadValue = LoadValue + 1, AccessCount = AccessCount + 1
        where ComponentId = '{}';
    """.format(result["ComponentId"])
    CSPDatabaseCursor.execute(query)

    startTimes[result["ComponentId"]] = int(time.time())

    response = app.response_class(
        response=json.dumps(result),
        status=200,
        mimetype='application/json'
    )

    logger.info("Allocated {} Component with componentId={} to tenant with tenantId={}".format(
        instanceOf, pformat(result), tenantId))
    return response

@app.route('/free-instance', methods=["POST"])
def freeInstance():
    ipAddress = request.json["IPAddress"]
    stopTime = int(time.time())
    query = """
        select ComponentId
        from Components
        where IPAddress = '{}'
    """.format(ipAddress)
    CSPDatabaseCursor.execute(query)
    componentId = CSPDatabaseCursor.fetchone()["ComponentId"]

    query = """
        update Loads
        set LoadValue = LoadValue - 1, ActiveTime = ActiveTime + {}
        where ComponentId = '{}' and LoadValue != 0
    """.format(stopTime - startTimes[componentId], componentId)
    CSPDatabaseCursor.execute(query)

    logger.info("Freed Component with ipAddress={}".format(ipAddress))
    
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

@app.route('/')
def hello_world():
    return 'This is the Load Balancer'

if __name__ == '__main__':
    app.run(debug=True,host='0.0.0.0', port=meta["AppPort"])
