import json
import pymysql
import requests
import logging.config
from time import sleep
from pathlib import Path
from pprint import pformat
from warnings import filterwarnings
from flask import Flask, json, jsonify, abort, make_response, request, url_for, redirect

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

meta = json.load(open("meta.json"))
filterwarnings('ignore', category=pymysql.Warning)
logging.config.fileConfig(str(Path("./log.conf")))
logger = logging.getLogger("root")

app = Flask(__name__)

def connectToWebRole():
	# request load balancer for the IP of a webrole
	# connect to the webrole
	# ??
	requestData = {
		"componentType": "WebRole",
		"tenantId": meta["tenantId"]
	}
	resp = requests.post(
		"http://{}/request-instance".format(meta["LoadBalancerIPAddress"]), json=requestData)
	logger.info("Obtained WebRole with IPAddress: {}".format(resp["IPAddress"]))

	return resp["IPAddress"]

@app.after_request
def add_header(r):
	""" Disable caching """
	r.headers["Cache-Control"] = "no-cache, no-store, must-revalidate, public, max-age=0"
	r.headers["Pragma"] = "no-cache"
	r.headers["Expires"] = "0"
	return r

@app.route('/set-host-meta', methods=['POST'])
def setTenantDetails():
	global meta
	meta["TenantId"] = request.json["tenantId"]
	meta["TenantName"] = request.json["tenantName"]
	meta["LoadBalancerIPAddress"] = request.json["loadBalancerIPAddress"]
	resp = {"status": 200, "message": "success"}
	logger.info("set-host-meta")
	return jsonify(resp)

# Forward all other URLs to WebRole of tenant
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def catch_all(path):
	requestData = {
		"componentType": "WebRole", 
		"tenantId": meta["TenantId"]
	}
	r = requests.post(
		"http://{}/request-instance".format(meta["LoadBalancerIPAddress"]), json=requestData)

	res = r.json()

	IPAddress = res["IPAddress"]
	HostIPAddress = res["HostIPAddress"]
	port = res["Port"]
	logger.info("got WebRole from LoadBalancer: {}".format(pformat(res)))
	
	if path:
		resp = redirect("http://{}:{}/{}".format(HostIPAddress, port, path))
	else:
		resp = redirect("http://{}:{}".format(HostIPAddress, port))

	requestData = {
		"IPAddress": IPAddress
	}
	sleep(3)
	r = requests.post(
		"http://{}/free-instance".format(meta["LoadBalancerIPAddress"]), json=requestData)
	res = r.json()

	return resp

@app.route('/check_alive')
def checkalive():
	responseMessage = {
		"status": "success"
	}
	return jsonify(responseMessage)

"""
@app.route('/')
def hello_world():
	return 'This is the HostApp'
"""

if __name__ == '__main__':
	app.run(debug=True,host='0.0.0.0', port=meta["AppPort"])
