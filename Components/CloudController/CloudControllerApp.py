import os
import time
import json
import docker
import socket
import pymysql
import requests
import subprocess
import logging.config
import pymysql.cursors
from git import Repo
from pathlib import Path
from hashlib import sha256
from shutil import copyfile
from warnings import filterwarnings
from flask import Flask, json, request, make_response, jsonify

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

meta = json.load(open("./Components/CloudController/meta.json"))
logging.config.fileConfig(str(Path("./Components/CloudController/log.conf")))
logger = logging.getLogger("root")

app = Flask(__name__)

CSPDatabaseCursor = pymysql.connect(
	host=meta["CSPDatabaseIPAddress"],
	user=meta["CSPDatabaseUsername"],
	port=3306,
	passwd=meta["CSPDatabasePassword"],
	autocommit=True
).cursor(pymysql.cursors.DictCursor)
CSPDatabaseCursor.execute("use {};".format(meta["CSPDatabaseName"]))

def createComponentContainer(componentName, componentType, IPAddress, tenantId, imageName):
	if componentType == "WebRole":
		cmd = "docker run --network=RainMakerNetwork --ip={} --name={} --expose 80 -P -d -v volume{}:/storage flask-{}".format(
			IPAddress, componentName, str(tenantId), imageName.lower())
	else:
		cmd = "docker run --network=RainMakerNetwork --ip={} --name={} -d -v volume{}:/storage flask-{}".format(
		IPAddress, componentName, str(tenantId), imageName.lower())
	containerId = subprocess.getoutput(cmd).split("\n")[-1]
	logger.info("Created Component container {}. IPAddress - {}, tenant - {}".format(componentName, IPAddress, tenantId))
	return containerId

#---------------------------Tenant-------------------------------------
@app.route("/authenticate", methods=['POST'])
def authenticateTenant():
	# verify if password hashes match and return the Token
	tenantEmailId, tenantPassword = request.json[
		"tenantEmailId"], request.json["tenantPassword"]
	h = sha256(bytes(tenantPassword, "utf-8")).hexdigest()
	CSPDatabaseCursor.execute("select PasswordHash as ph, TenantId as tenantId, Name as tenantName from Tenants where EmailId='{}'".format(tenantEmailId))
	result = CSPDatabaseCursor.fetchone()

	if result and result["ph"] == h:
		token = {
			"tenantId": result["tenantId"],
			"encrypted": result["tenantId"],
			"tenantName": result["tenantName"]
		}
		responseMessage = {
			"status": "success",
			"message": token
		}
		logger.info("Tenant {} Authenticated".format(result["tenantName"]))
	else:
		responseMessage = {
			"status": "error",
			"message": "Invalid login credentials"
		}
		logger.info("Tenant {} Authentication failed".format(tenantEmailId))
	
	response = app.response_class(
		response=json.dumps(responseMessage),
		status=200,
		mimetype='application/json'
	)

	return response

@app.route("/register-tenant", methods=['POST'])
def registerTenant():
	# Get Name, Password
	tenantName = request.json["tenantName"]
	tenantPassword = request.json["tenantPassword"]
	emailId = request.json["tenantEmailId"]

	# Create password hash; obtain Subnet, Port, LatestIPAddress
	passwordHash = sha256(str.encode(tenantPassword)).hexdigest()
	query = "select Subnet from Tenants;"
	CSPDatabaseCursor.execute(query)
	results = CSPDatabaseCursor.fetchall()
	nextIPAddress = results[0]["Subnet"].split(".")
	nextIPAddress[1] = str(max(int(i["Subnet"].split(".")[1]) for i in results) + 1)
	nextSubnet = ".".join(nextIPAddress)

	# insert the next row
	query = "insert into Tenants (Name, EmailId, PasswordHash, Subnet) values('{}', '{}', '{}', '{}')".format(
		tenantName, emailId, passwordHash, nextSubnet)
	CSPDatabaseCursor.execute(query)
	logger.info("Created new tenant {}".format(tenantName))

	# get tenantId from database (auto-generated)
		# CSPDatabaseCursor.execute("select MAX(TenantId) as newTenantId from Tenants;")
		# tenantId = CSPDatabaseCursor.fetchone()['newTenantId']
	tenantId = CSPDatabaseCursor.lastrowid

	# add PortSeries to new tenant entry
	publicPort = tenantId + meta["Parameters"]["PortSeriesOffset"]
	query = "update Tenants set PublicPort={} where TenantId={}".format(
		publicPort, tenantId)
	CSPDatabaseCursor.execute(query)
	logger.info("PublicPort added to new tenant")

	# create new volume and update Volumes table
	os.system("docker volume create volume" + str(tenantId))
	cmd = "docker volume inspect volume" + str(tenantId)
	output = subprocess.getoutput(cmd)
	hostPath = json.loads(output)[0]["Mountpoint"]

	if not hostPath[-1] == "/":
		hostPath += "/"

	query = """
		insert into Volumes (VolumeName, TenantId, HostPath)
		values ('{}', {}, '{}');
	""".format("volume" + str(tenantId), tenantId, hostPath)
	CSPDatabaseCursor.execute(query)
	logger.info("Created new volume {}".format("volume" + str(tenantId)))

	# create data directory in tenant's volume, where fetched training data will be stored
	if not os.path.exists(hostPath + "data"):
		os.mkdir(hostPath + "data")

	# create a database for the tenant in the TenantsDatabase
	query = "select IPAddress from Components where ComponentName='TenantDatabase' and TenantId=1"
	CSPDatabaseCursor.execute(query)
	tenantDatabaseIPAddress = CSPDatabaseCursor.fetchone()['IPAddress']

	databaseConnection = pymysql.connect(
		host=tenantDatabaseIPAddress,
		user="root",
		passwd=meta["DatabaseRootPassword"],
		port=3306,
		autocommit=True
	)
	tenantDatabaseCursor = databaseConnection.cursor(pymysql.cursors.DictCursor)

	createDatabasesCMD = "drop database if exists {database};create database {database};"
	tenantDatabaseCursor.execute(createDatabasesCMD.format(**{
		"database": tenantName
	}))
	logger.info("Created new database for tenant in TenantDatabase")

	# set Host's IPAddress as the first IP in the x.x.0.0/16 subnet
	hostIPAddress = nextSubnet[:-3].split(".")
	hostIPAddress[2] = hostIPAddress[3] = "1"
	hostIPAddress = ".".join(hostIPAddress)
	componentName = "Host" + str(tenantId)

	# deploy host container, add to the Components table
	cmd = "docker run --network=RainMakerNetwork --ip={} --name={} -d -p {}:{} -v volume{}:/storage flask-host".format(
		hostIPAddress, componentName, meta["Parameters"]["PortSeriesOffset"] + tenantId, meta["AppPort"], str(tenantId))
	containerId = subprocess.getoutput(cmd).split("\n")[-1]
	
	# send LoadBalancer details, tenantName and tenantId to new Host
	CSPDatabaseCursor.execute("select IPAddress from Components where ComponentName='LoadBalancer'")
	loadBalancerIPAddress = CSPDatabaseCursor.fetchone()["IPAddress"]
	hostDetails = {
		"tenantId": tenantId,
		"tenantName": tenantName,
		"loadBalancerIPAddress": loadBalancerIPAddress
	}
	time.sleep(3)
	requests.post("http://{}/set-host-meta".format(hostIPAddress), json=hostDetails)

	# insert new Host's details to the Components table
	query = """
		insert into Components (ComponentId, ComponentName, IPAddress, TenantId, Type) values
		('{}', '{}', '{}', {}, '{}');
	""".format(containerId, componentName, hostIPAddress, tenantId, "Host")
	CSPDatabaseCursor.execute(query)

	logger.info("Created Host container {}. IPAddress - {}, tenant - {}".format(
		componentName, hostIPAddress, tenantId))

	responseMessage = {
		"status": "success"
	}
	response = app.response_class(
		response=json.dumps(responseMessage),
		status=200,
		mimetype='application/json'
	)
	return response

@app.route("/new-component", methods=['POST'])
def createComponent():
	tenantId, componentType, numOfComponents = request.json["tenantId"], request.json["componentType"], request.json["numOfComponents"]
	responseMessage = None
	containerIds = []
	query = """
			select Subnet
			from Tenants
			where TenantId = {}
		""".format(tenantId)
	CSPDatabaseCursor.execute(query)
	nextIPAddress = CSPDatabaseCursor.fetchone()["Subnet"][:-3].split(".")

	if componentType == "WebRole":
		# obtain latest WebRole name
		nextIPAddress[2] = "2"
		query = """
			select count(*) as Count
			from Components
			where TenantId = {} and Type='WebRole'
		""".format(tenantId)
		CSPDatabaseCursor.execute(query)
		webRoleCount = CSPDatabaseCursor.fetchone()["Count"]

		# insert into Components
		query = "insert into Components (ComponentId, ComponentName, IPAddress, TenantId, Type) values"
		for i in range(1, numOfComponents+1):
			nextIPAddress[3] = str(webRoleCount + i)
			finalIPAddress = ".".join(nextIPAddress)
			containerIds.append(createComponentContainer(
				"WebRole" + str(tenantId) + "_" + str(webRoleCount + i), "WebRole", finalIPAddress, tenantId, "WebRole" + str(tenantId)))
			query += "('{}', '{}', '{}', {}, 'WebRole'),".format(
				containerIds[i - 1], "WebRole" + str(webRoleCount + i), finalIPAddress, tenantId)
		query = query[:-1] + ";"
		CSPDatabaseCursor.execute(query)
		logger.info("Inserted {} components to the Compoents Table for tenant {}".format(numOfComponents, tenantId))

		# insert into Loads table
		query = "insert into Loads(ComponentId, LoadValue, ActiveTime, AccessCount) values "
		for i in range(1, numOfComponents+1):
			row = "('{}', 0, 0, 0),".format(containerIds[i - 1])
			query += row
		query = query[:-1] + ";"
		CSPDatabaseCursor.execute(query)
		logger.info("Inserted {} values to the Loads Table for tenant {}".format(numOfComponents, tenantId))

	elif componentType == "WorkerRole":
		nextIPAddress[2] = "3"
		query = """
			select count(*) as Count
			from Components
			where TenantId = {} and Type='WorkerRole'
		""".format(tenantId)
		CSPDatabaseCursor.execute(query)
		workerRoleCount = CSPDatabaseCursor.fetchone()["Count"]

		# insert into Components
		query = "insert into Components (ComponentId, ComponentName, IPAddress, TenantId, Type) values"
		for i in range(1, numOfComponents + 1):
			nextIPAddress[3] = str(workerRoleCount + i)
			finalIPAddress = ".".join(nextIPAddress)
			containerIds.append(createComponentContainer(
				"WorkerRole" + str(tenantId) + "_" + str(workerRoleCount + i), "WorkerRole", finalIPAddress, tenantId, "WorkerRole" + str(tenantId)))
			query += "('{}', '{}', '{}', {}, 'WorkerRole'),".format(
				containerIds[i - 1], "WorkerRole" + str(workerRoleCount + i), finalIPAddress, tenantId)
		query = query[:-1] + ";"
		CSPDatabaseCursor.execute(query)
		logger.info("Inserted {} components to the Compoents Table for tenant {}".format(numOfComponents, tenantId))
		
		# insert into Loads table
		query = "insert into Loads(ComponentId, LoadValue, ActiveTime) values "
		for i in range(1, numOfComponents + 1):
			row = "('{}', 0, 0),".format(containerIds[i -1])
			query += row
		query = query[:-1] + ";"
		CSPDatabaseCursor.execute(query)
		logger.info("Inserted {} values to the Loads Table for tenant {}".format(numOfComponents, tenantId))
		
	responseMessage = {
		"status": "success",
		"message": "Created components"
	}

	response = app.response_class(
		response=json.dumps(responseMessage),
		status=200,
		mimetype='application/json'
	)
	return response

@app.route('/create-webapp-images', methods=['POST'])
def createWebAppImages():
	url = request.json["url"]
	tenantId = request.json["tenantId"]

	# get the host path of tenant volume
	CSPDatabaseCursor.execute("select HostPath from Volumes where TenantId={};".format(tenantId))
	hostPath = CSPDatabaseCursor.fetchone()["HostPath"]
	if not hostPath[-1] == "/":
		hostPath += "/"

	logger.info(hostPath)

	# git clone the WebRole and WorkerRole
	Repo.clone_from(url, hostPath + "WebApp")
	logger.info("Git cloned the repository for tenant {}".format(tenantId))
	 
	# add meta.json and rainmaker.py for WebRole and WorkerRole
	CSPDatabaseCursor.execute("select IPAddress from Components where ComponentName='DatabaseAccessController';")
	DBACIPAddress = CSPDatabaseCursor.fetchone()["IPAddress"]
	CSPDatabaseCursor.execute("select IPAddress from Components where ComponentName='LoadBalancer';")
	loadBalancerIPAddress = CSPDatabaseCursor.fetchone()["IPAddress"]
	meta = {
		"IPAddresses": {
			"DatabaseAccessController": DBACIPAddress,
			"LoadBalancer": loadBalancerIPAddress
		},
		"TenantId": tenantId
	}
	confPath = hostPath + "/WebApp/WebRole/meta.json"
	with open(confPath, "w+") as f:
		f.write(json.dumps(meta, indent=4))
	confPath = hostPath + "/WebApp/WorkerRole/meta.json"
	with open(confPath, "w+") as f:
		f.write(json.dumps(meta, indent=4))
    
    # copy rainmaker.py to WebApp
	copyfile("./Components/WebApp/rainmaker.py", hostPath + "/WebApp/WebRole/rainmaker.py")
	copyfile("./Components/WebApp/rainmaker.py", hostPath + "/WebApp/WorkerRole/rainmaker.py")
	logger.info("Added meta.json and rainmaker.py for WebRole and WorkerRole of tenant{}".format(tenantId))

	# create webrole image
	imageName = "webrole" + str(tenantId)
	os.system("docker build -t flask-{}:latest {}".format(imageName, hostPath + "WebApp" + "/WebRole" ))
	logger.info("Created WebRole image for {}".format(imageName))

	# create workerrole image
	imageName = "workerrole" + str(tenantId)
	os.system("docker build -t flask-{}:latest {}".format(imageName, hostPath + "WebApp" + "/WorkerRole" ))
	logger.info("Created WorkerRole image for {}".format(imageName))

	responseMessage = {
		"status": "success"
	}
	response = app.response_class(
		response=json.dumps(responseMessage),
		status=200,
		mimetype='application/json'
	)
	return response

@app.route('/get-port', methods=['POST'])
def getPort():
    componentId = request.json["componentId"] 
    cmd = "docker port {}".format(componentId)
    result = subprocess.getoutput(cmd).split(":")[-1]
    return jsonify(result)

@app.route('/get-docker-stats', methods=['POST'])
def dockerStats():
	tenantId = request.json["tenantId"]
	componentType = request.json["componentType"]
	query = """
		select ComponentId, ComponentName from Components where TenantId = {} and Components.Type = '{}';
	""".format(tenantId, componentType)
	CSPDatabaseCursor.execute(query)
	results = CSPDatabaseCursor.fetchall()
	client = docker.from_env()

	results = [i for i in results if i["ComponentName"]
            not in ["MLController", "CloudController"]]

	dockerStats = {}

	for i in results:
		container = client.containers.get(i["ComponentId"])
		stat = container.stats(stream=False)

		cpu_count = len(stat["cpu_stats"]["cpu_usage"]["percpu_usage"])
		cpu_percent = 0.0
		cpu_delta = float(stat["cpu_stats"]["cpu_usage"]["total_usage"]) - \
                    float(stat["precpu_stats"]["cpu_usage"]["total_usage"])
		system_delta = float(stat["cpu_stats"]["system_cpu_usage"]) - \
                    float(stat["precpu_stats"]["system_cpu_usage"])
		if system_delta > 0.0:
			cpu_percent = cpu_delta / system_delta * 100.0 * cpu_count

		dockerStats[i["ComponentName"]] = {
			"cpu": cpu_percent,
			"memory": stat["memory_stats"]["usage"] / stat["memory_stats"]["limit"] * 100.0
		}
	return jsonify({'status': 'success', 'message': dockerStats})


@app.route('/')
def hello_world():
	return 'This is the CloudControllerApp'

if __name__ == '__main__':
	app.run(host='0.0.0.0', port=meta["CloudControllerPort"])
