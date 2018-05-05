import os
import json
import time
import socket
import pymysql
import requests
import subprocess
import logging.config
import pymysql.cursors
from pathlib import Path
from hashlib import sha256
from shutil import copyfile
from warnings import filterwarnings
from multiprocessing import Process

confPath = "./Setup/conf.json"
MLPath = Path("./ML/")
componentsPath = Path("./Components/")
logging.config.fileConfig(str(Path("./Setup/log.conf")))
logger = logging.getLogger("root")

def initConfigurations(confPath):
	# read the configuration file
	with open(confPath, "r") as confFile:
		confs = json.load(confFile)
	logger.info("Read the configurations file successfully")

	# obtain IP address of the Host machine
	s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	s.connect(("8.8.8.8", 80))
	hostIPAddress = s.getsockname()[0]
	s.close()
	logger.info("Obtained IP address of the Host machine : {}".format(hostIPAddress))

	# update the configuration file with the Host IP Address
	confs["IPAddress"]["CloudController"] = hostIPAddress
	confs["IPAddress"]["MLController"] = hostIPAddress
	
	# TODO: uncomment the following while running it
	# commented because it causes git merge issues when pulling 
	# as the conf.json file is being changed at runtime.
	"""
	with open(confPath, "w+") as f:
			f.write(json.dumps(confs, indent=4))
	logger.info("Updated the configuration file with the Host IP Address")
	"""
	
	meta = {
		"CSPDatabaseIPAddress": confs["IPAddress"]["CSPDatabase"],
		"CSPDatabaseName": confs["Database"]["CSPDatabaseName"],
		"CSPDatabaseUsername": confs["Database"]["CSPDatabaseUsername"],
		"CSPDatabasePassword": confs["Database"]["CSPDatabasePassword"],
		"DatabaseRootPassword": confs["Database"]["DatabaseRootPassword"],
		"AppPort": confs["Port"]["AppPort"],
		"Parameters": confs["Parameters"],
		"CloudControllerPort": confs["Port"]["CloudController"],
		"MLControllerPort": confs["Port"]["MLController"],
		"HealthMonitor": confs["HealthMonitor"]
	}

	# write CSP Database IP  to Dashboard, CloudController, MLController
	# LoadBalancer, HealthMonitor MLController, MLTrainer and MLPredictor
	components = ["Dashboard", "LoadBalancer", "HealthMonitor", "MLTrainer", "MLPredictor", "CloudController", "MLController"]
	paths = [ componentsPath / i / "meta.json" for i in components ]
	for row in paths:
		with row.open("w+") as f:
			f.write(json.dumps(meta, indent=4))

	for i in components:
		logger.info("Created meta.json for {}".format(i))

	# write Tenant Database details to DatabaseAccessController.
	meta = {
		"TenantDatabaseIPAddress": confs["IPAddress"]["TenantDatabase"],
		"TenantDatabaseName": confs["Database"]["TenantDatabaseName"], 
		"TenantDatabasePassword": confs["Database"]["TenantDatabasePassword"], 
		"TenantDatabaseUsername": confs["Database"]["TenantDatabaseUsername"],
		"AppPort": confs["Port"]["AppPort"]
	}
	with (componentsPath / "DatabaseAccessController" / "meta.json").open("w+") as f:
			f.write(json.dumps(meta, indent=4))
	logger.info("Created meta.json for DatabaseAccessController")
	
	# write AppPort to HostContainer
	meta = {
		"AppPort": confs["Port"]["AppPort"]
	}
	with (componentsPath / "Host" / "meta.json").open("w+") as f:
			f.write(json.dumps(meta, indent=4))
	logger.info("Created meta.json for Host")

	return confs

def createRainMakerNetwork(IPAddress):
	cmd = "docker network create -d bridge --subnet {} RainMakerNetwork".format(IPAddress)
	os.system(cmd)
	logger.info("Created RainMaker Network. IPAddress - {}".format(IPAddress))

def createAndInitializeDatabase(CSPDatabaseIPAddress, TenantDatabaseIPAddress, databaseConfs):
	# run the docker command to create the database with the appropriate parameters
	CSPDatabaseCmd = "docker run --network=RainMakerNetwork --ip={} --name=CSPDatabase -e MYSQL_ROOT_PASSWORD={} -d mysql:5.7".format(
		CSPDatabaseIPAddress,
		databaseConfs["DatabaseRootPassword"]
	)

	tenantDatabaseCmd = "docker run --network=RainMakerNetwork --ip={} --name=TenantDatabase -e MYSQL_ROOT_PASSWORD={} -d mysql:5.7".format(
		TenantDatabaseIPAddress,
		databaseConfs["DatabaseRootPassword"]
	)
	
	CSPDatabaseContainerId = subprocess.getoutput(CSPDatabaseCmd).split("\n")[-1]
	TenantDatabaseContainerId = subprocess.getoutput(
		tenantDatabaseCmd).split("\n")[-1]
	logger.info("Created CSPDatabase({}) and TenantDatabase({})".format(CSPDatabaseContainerId, CSPDatabaseContainerId))

	# wait for Database container to initalize (ready to accept connections)
	
	cmd = """
		while ! mysqladmin ping -h"{}" --silent; do
			sleep 0.1
		done
		echo "Ready"
	"""

	# cmd = """
	# 	until nc -z -v -w30 {} 3306 
	# 	do
	# 		sleep 0.1
	# 	done
	# 	echo "Ready"
	# """
	logger.info("Waiting for Databases to respond...")
	subprocess.getoutput(cmd.format(CSPDatabaseIPAddress))
	subprocess.getoutput(cmd.format(TenantDatabaseIPAddress))

	# create user in the CSPDatbase
	filterwarnings('ignore', category = pymysql.Warning)
	databaseConnection = pymysql.connect(
		host = CSPDatabaseIPAddress,
		user = "root",
		passwd = databaseConfs["DatabaseRootPassword"],
		autocommit = True
	)
	databaseCursor = databaseConnection.cursor(pymysql.cursors.DictCursor)

	createUsersCMD = "create user '{user}'@'%' identified by '{password}';"
	databaseCursor.execute(createUsersCMD.format(**{
		"user": databaseConfs["CSPDatabaseUsername"],
		"password": databaseConfs["CSPDatabasePassword"]
	}))

	# create the database
	createDatabasesCMD = "drop database if exists {};"
	databaseCursor.execute(createDatabasesCMD.format(databaseConfs["CSPDatabaseName"]))
	createDatabasesCMD = "create database {};"
	databaseCursor.execute(createDatabasesCMD.format(databaseConfs["CSPDatabaseName"]))

	useDatabaseCMD = "use {};".format(databaseConfs["CSPDatabaseName"])
	databaseCursor.execute(useDatabaseCMD)

	privilegesCMD = "grant all privileges on {}.* to '{}'@'%';".format(databaseConfs["CSPDatabaseName"], databaseConfs["CSPDatabaseUsername"])
	databaseCursor.execute(privilegesCMD)
	privilegesCMD = "flush privileges"
	databaseCursor.execute(privilegesCMD)

	databaseCursor = pymysql.connect(
		host=CSPDatabaseIPAddress,
		user=databaseConfs["CSPDatabaseUsername"],
		passwd=databaseConfs["CSPDatabasePassword"],
		autocommit=True
	).cursor(pymysql.cursors.DictCursor)

	logger.info("Databases Ready")
	
	return (databaseCursor, CSPDatabaseContainerId, TenantDatabaseContainerId)

def createTables(CSPDatabaseCursor, CSPDatabaseName):
	query = "use {};".format(CSPDatabaseName)
	CSPDatabaseCursor.execute(query)

	# create the Tenants table
	query = """
		create table Tenants(
			TenantId SMALLINT AUTO_INCREMENT,
			Name VARCHAR(50),
			EmailId VARCHAR(100),
			PasswordHash CHAR(64),
			Subnet VARCHAR(18),
			PublicPort INT,

			primary key (TenantId)
		);
	"""
	CSPDatabaseCursor.execute(query)
	logger.info("Created Tenants table")

	# create the Volumes table
	query = """
		create table Volumes( 
			VolumeId SMALLINT AUTO_INCREMENT,
			VolumeName VARCHAR(50),
			TenantId SMALLINT,
			HostPath VARCHAR(200),

			primary key (VolumeId),
			foreign key (TenantId) references Tenants(TenantId)
		);
	"""
	CSPDatabaseCursor.execute(query)
	logger.info("Created Volumes table")

	# create the Components table
	query = """
		create table Components(
			ComponentId CHAR(64),
			ComponentName VARCHAR(100),
			IPAddress VARCHAR(15),
			TenantId SMALLINT,
			Type VARCHAR(100),

			primary key (ComponentId),
			foreign key (TenantId) references Tenants(TenantId)
		);
	"""
	CSPDatabaseCursor.execute(query)
	logger.info("Created Components table")

	# create the Loads table
	query = """
		create table Loads(
			ComponentId CHAR(64),
			LoadValue INT,
			ActiveTime INT,
			AccessCount INT DEFAULT 0,

			primary key (ComponentId),
			foreign key (ComponentId) references Components(ComponentId)
		);
	"""
	CSPDatabaseCursor.execute(query)
	logger.info("Created Loads table")

	# create the Models table
	query = """
		create table Models(
			ModelId INT AUTO_INCREMENT,
			ModelName VARCHAR(100),
			Description VARCHAR(1000),
			Type VARCHAR(20),
			
			primary key (ModelId)
		);
	"""
	CSPDatabaseCursor.execute(query)
	logger.info("Created Models table")

	# create the PretrainedModels table
	query = """
		create table PretrainedModels(
			PretrainedModelId INT AUTO_INCREMENT,
			ModelId INT,
			ContainerConfPath VARCHAR(200),
			
			primary key (PretrainedModelId),
			foreign key (ModelId) references Models(ModelId)
		);
	"""
	CSPDatabaseCursor.execute(query)
	logger.info("Created PretrainedModels table")

	# create the TenantTrainedModels table
	query = """
		create table TenantTrainedModels(
			TenantTrainedModelId INT AUTO_INCREMENT,
			ModelId INT,
			TenantId SMALLINT,
			ContainerConfPath VARCHAR(200),
			
			primary key (TenantTrainedModelId),
			foreign key (ModelId) references Models(ModelId),
			foreign key (TenantId) references Tenants(TenantId) 
		);
	"""
	CSPDatabaseCursor.execute(query)
	logger.info("Created TenantTrainedModels table")

	query = """
		create table Predictors(
			PredictorId INT AUTO_INCREMENT,
			ComponentId CHAR(64),
			TenantId SMALLINT,
			ModelId INT,

			primary key (PredictorId),
			foreign key (ComponentId) references Components(ComponentId),
			foreign key (ModelId) references Models(ModelId),
			foreign key (TenantId) references Tenants(TenantId) 
		);
	"""
	CSPDatabaseCursor.execute(query)
	logger.info("Created Predictors table")

def updateCSPDatabase(CSPDatabaseCursor, componentDetails, confs, volumeConf):
	query = "use {};".format(confs["Database"]["CSPDatabaseName"])
	CSPDatabaseCursor.execute(query)

	# insert CSP to Tenants table
	h = sha256(bytes(confs["CSP"]["Password"], "utf-8")).hexdigest()
	CSPSubnet = confs["IPAddress"]["RainMaker"]
	query = """
		insert into Tenants (TenantId, Name, EmailId, PasswordHash, Subnet, PublicPort)
		values (1, '{}', '{}', '{}', '{}', {});
	""".format(confs["CSP"]["Username"], confs["CSP"]["EmailId"], h, CSPSubnet, 9000)	# TODO: change public port for CSP
	CSPDatabaseCursor.execute(query)
	logger.info("Added CSP to Tenants table")

	# insert CSP Volume to the Volumes table
	query = """
		insert into Volumes (VolumeName, TenantId, HostPath)
		values ('{}', '{}', '{}');
	""".format(volumeConf["volumeName"], volumeConf["tenantId"], volumeConf["hostPath"])
	CSPDatabaseCursor.execute(query)
	logger.info("Added CSP Volume to Volumes table")

	# insert CSP components into Components Table
	query = "insert into Components (ComponentId, ComponentName, IPAddress, TenantId, Type) values "
	for componentName in componentDetails:
		logger.info("{}, {}".format(componentName, componentDetails[componentName]))
		query += "('{}', '{}', '{}', 1, '{}'),".format(
			componentDetails[componentName],
			componentName,
			confs["IPAddress"][componentName],
			componentName
		)
	query = query.rstrip(',') + ";"
	CSPDatabaseCursor.execute(query)
	logger.info("Added CSP components to Components table")

def createVolume(tenantId):
	os.system("docker volume create volume" + str(tenantId))
	cmd = "docker volume inspect volume" + str(tenantId)
	output = subprocess.getoutput(cmd)
	hostPath = json.loads(output)[0]["Mountpoint"]

	if not hostPath[-1] == "/":
		hostPath += "/"

	return {
		"hostPath": hostPath,
		"volumeName": "volume" + str(tenantId),
		"tenantId": str(tenantId)
	}
	logger.info("Created Volume for tenant {}".format(tenantId))

def createImage(componentName):
	os.chdir(str(componentsPath / componentName))
	os.system("docker build -t flask-{}:latest .".format(componentName.lower()))
	os.chdir("../..")
	logger.info("Created Component image for {}".format(componentName))

def createMLImage(CSPDatabaseCursor, MLModelName, description):
	# create the image and obtain imageRepo
	os.chdir(str(MLPath / "Untrained" / MLModelName))
	os.system("docker build -t flask-{}:latest .".format(MLModelName.lower()))
	cmd = "docker images flask-{}".format(MLModelName)
	imageRepo = subprocess.getoutput(cmd).split("\n")[-1].split()[2]

	# copy JSON hyper-parameter conf file to CSP Volume
	query = """
		select HostPath from Volumes
		where TenantId = 1;
	"""
	CSPDatabaseCursor.execute(query)
	hostPath = CSPDatabaseCursor.fetchone()["HostPath"]
	containerConfPath = Path(hostPath) / MLModelName
	if not os.path.exists(str(containerConfPath)):
		os.makedirs(str(containerConfPath))
	copyfile("paramConf.json", str(containerConfPath / "paramConf.json"))
	os.chdir("../..")

	# update the Models table
	query = """
		insert into Models (ModelName, Type, Description)
		values ('{}', '{}', '{}')
	""".format(MLModelName, "Untrained", description)
	logger.info("Created ML Untrained image for {}".format(MLModelName))

def createComponent(componentName, IPAddress, tenantId, ports):
	if ports:
		cmd = "docker run --network=RainMakerNetwork --ip={} --name={} -d -p {}:{} -v volume{}:/storage flask-{}".format(
		IPAddress, componentName, ports[0], ports[1], str(tenantId), componentName.lower())
	else:
		cmd = "docker run --network=RainMakerNetwork --ip={} --name={} -d -v volume{}:/storage flask-{}".format(
                    IPAddress, componentName, str(tenantId), componentName.lower())
	containerId = subprocess.getoutput(cmd).split("\n")[-1]
	logger.info("Created Component container {}. IPAddress - {}, tenant - {}".format(componentName, IPAddress, tenantId))
	return containerId

def startControllerComponent(componentName):
	cmd = "pip3 install -r ./Components/{}/Requirements.txt".format(componentName)
	os.system(cmd)
	cmd = "python3 ./Components/{componentName}/{componentName}App.py".format(**{"componentName": componentName})
	os.system(cmd + " &")
	logger.info("Created Host Component container {}".format(componentName))
	return componentName

def main():
	componentDetails = {}
	startTime = time.time()

	# read the configuration file (and update the IPAddress for the Controllers as the local IPAddress)
	confs = initConfigurations(confPath)
	print("Completed configuration init")
	logger.info("Completed configuration init")

	# create the RainMaker Network
	createRainMakerNetwork(confs["IPAddress"]["RainMaker"])
	print("Created the RainMaker Network")
	logger.info("Created the RainMaker Network")

	# create the CSP Volume
	volumeConf = createVolume(1)
	print("Created the CSP Volume")
	logger.info("Created the CSP Volume")

	# create all RainMaker images
	createImage("Dashboard")
	createImage("LoadBalancer")
	createImage("DatabaseAccessController")
	createImage("HealthMonitor")
	createImage("MLTrainer")
	createImage("MLPredictor")
	createImage("Host")

	print("Created the CSP Images")
	logger.info("Created the CSP Images")

	# create all components
	CSPDatabaseCursor, componentDetails["CSPDatabase"], componentDetails["TenantDatabase"] = createAndInitializeDatabase(
		confs["IPAddress"]["CSPDatabase"],
		confs["IPAddress"]["TenantDatabase"],
		confs["Database"]
	)
	
	# TODO: remove ports after debugging (except Dashboard)
	componentDetails["Dashboard"] = createComponent("Dashboard", confs["IPAddress"]["Dashboard"], 1, (confs["Port"]["Dashboard"], confs["Port"]["AppPort"]))
	componentDetails["LoadBalancer"] = createComponent("LoadBalancer", confs["IPAddress"]["LoadBalancer"], 1, (9002, 80))
	componentDetails["DatabaseAccessController"] = createComponent("DatabaseAccessController", confs["IPAddress"]["DatabaseAccessController"], 1, (9003, 80))
	componentDetails["HealthMonitor"] = createComponent("HealthMonitor", confs["IPAddress"]["HealthMonitor"], 1, (9004, 80))
	print("Created the CSP Component containers...")
	logger.info("Created the CSP Component containers...")

	# start CloudController and MLController
	componentDetails["CloudController"] = startControllerComponent("CloudController")
	componentDetails["MLController"] = startControllerComponent("MLController")
	print("Started CloudController and MLController...")
	logger.info("Started CloudController and MLController...")

	# create CSP tables in CSP Database
	createTables(CSPDatabaseCursor, confs["Database"]["CSPDatabaseName"])
	print("Created CSP tables")
	logger.info("Created CSP tables")

	# add CSP data to the created tables
	updateCSPDatabase(CSPDatabaseCursor, componentDetails, confs, volumeConf)
	print("Updated CSP tables")
	logger.info("Updated CSP tables")

	# initalize Dashboard
	requests.get("http://{}/obtain-ip-addresses".format(confs["IPAddress"]["Dashboard"]))

	# start HealthMonitor service
	try:
		requests.get(
			"http://{}/start-healthmonitor".format(confs["IPAddress"]["HealthMonitor"]), timeout=1)
	except:
		logger.info("Started HealthMonitor service")

	print("Done!")

	timeTaken = time.time() - startTime
	print("Time taken : {}".format(str(timeTaken)))
	logger.info("Time taken : {}".format(str(timeTaken)))

main()
