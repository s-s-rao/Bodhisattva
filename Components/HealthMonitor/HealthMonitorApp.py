import os
import json
import pymysql
import requests
import logging.config
from time import sleep
from pathlib import Path
from pprint import pformat
from flask import Flask, request
from warnings import filterwarnings

app = Flask(__name__)
meta = json.load(open("meta.json"))

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

filterwarnings('ignore', category = pymysql.Warning)
logging.config.fileConfig(str(Path("./log.conf")))
logger = logging.getLogger("root")

databaseCursor = pymysql.connect(
	host=meta["CSPDatabaseIPAddress"],
	user=meta["CSPDatabaseUsername"],
	passwd=meta["CSPDatabasePassword"],
	port=3306,
	autocommit=True
).cursor(pymysql.cursors.DictCursor)
databaseCursor.execute("use {};".format(meta["CSPDatabaseName"]))

trackFailures = {}
healthMonitorStarted = False

def heartbeat():
	# get IPs of all Components from CSPDatabase
	# ping each IP and note the response (only failed ones)
	# if any have failed notify the Dashboard - report ComponentId
	# else, notify to the Dashboard that all components are fine
	# use the heartbeat API call to communicate with Dashboard.

	query = """
		select IPAddress, ComponentId, TenantId, ComponentName from Components
		ORDER BY TenantId;
	"""
	query1 = """
		select IPAddress from Components
		where ComponentName = 'Dashboard';
	"""
	databaseCursor.execute(query)
	results = databaseCursor.fetchall()

	databaseCursor.execute(query1)
	results1 = databaseCursor.fetchone()

	failedComponents = []

	for i in results:
		ipAddress = i["IPAddress"]
		componentId = i["ComponentId"]

		if i["ComponentName"] == "HealthMonitor":
			pass
		elif not (i["ComponentName"] in ["MLController", "CloudController", "CSPDatabase", "TenantDatabase"]):
			resp = True
			try:
				requests.get("http://{}/check_alive".format(ipAddress), timeout=1)
			except:
				resp = False
		else:
			response = os.system("ping -c 1 " + ipAddress)
			resp = response == 0

		if componentId not in trackFailures:
			trackFailures[componentId] = 1
		
		# ping failed
		if not resp:
			trackFailures[componentId] += 1
			if trackFailures[componentId] >= meta['HealthMonitor']['RetriesBeforeFailure']:
				failedComponents.append(
					[i["TenantId"], i["ComponentId"], ipAddress])
				trackFailures.pop(componentId)
			logger.info("Ping failed for: \n{}".format(pformat(failedComponents)))

	if failedComponents:
		responseMessage = {
			"status" : "failed",
			"failedComponents": failedComponents
		}
	else:
		responseMessage = {
			"status" : "success"
		}
	requests.post(
		"http://{}/heartbeat-response".format(results1["IPAddress"]), json=responseMessage)

@app.route("/start-healthmonitor")
def startHealthMonitor():
	global healthMonitorStarted
	if not healthMonitorStarted:
		healthMonitorStarted = True
		logger.info("HealthMonitor started...")
		while True:
			heartbeat()
			sleep(meta["HealthMonitor"]["HeartbeatInterval"])

@app.route('/')
def hello_world():
	return 'This is the HealthMonitorApp'

if __name__ == '__main__':
	app.run(debug=True,host='0.0.0.0', port=meta["AppPort"])
