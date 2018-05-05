graphUsersOverTime = null;
dataUsersOverTime = [];
dataInstancesActiveTime = [];
// dataInstancesActiveTime = [{instance: "hi", time: 10}];
dataInstancesStats = [];
// dataInstancesStats = [{instance: "hi", cpu: 10, memory: 2.5}];

function fetchNumHits() {
	var xhr = new XMLHttpRequest();
	xhr.onreadystatechange = function () {
		if (xhr.readyState == XMLHttpRequest.DONE) {
			output = xhr.responseText;
			output = JSON.parse(output);
			resp = output["status"];
			if(resp == 200 || resp == "success") {
				div = document.getElementById("num-hits");
				div.innerHTML = output["message"];
			}
			else {
				;
			}
		}
	}
	xhr.open('POST', '/api/webapp-clicks');
	xhr.setRequestHeader('Content-type', 'application/json');
	// xhttp.setRequestHeader('Access-Control-Request-Headers', 'content-type');
	// xhttp.setRequestHeader('Access-Control-Request-Method', 'POST');
	req = {
		"tenantId": token["tenantId"]
	}
	xhr.send(JSON.stringify(req));
}

function fetchNumActiveUsers() {
	var xhr = new XMLHttpRequest();
	xhr.onreadystatechange = function () {
		if (xhr.readyState == XMLHttpRequest.DONE) {
			output = xhr.responseText;
			output = JSON.parse(output);
			resp = output["status"];
			if(resp == 200 || resp == "success") {
				div = document.getElementById("num-active-users");
				div.innerHTML = output["message"];

				now = new Date().getTime();
				newData = {
					timestamp: now,
					value: output["message"]
				};
				dataUsersOverTime.push(newData);
			}
			else {
				;
			}
		}
	}
	xhr.open('POST', '/api/active-users');
	xhr.setRequestHeader('Content-type', 'application/json');
	// xhttp.setRequestHeader('Access-Control-Request-Headers', 'content-type');
	// xhttp.setRequestHeader('Access-Control-Request-Method', 'POST');
	req = {
		"tenantId": token["tenantId"]
	}
	xhr.send(JSON.stringify(req));
}

function fetchDataInstancesActiveTimeWebRoles() {
	var xhr = new XMLHttpRequest();
	xhr.onreadystatechange = function () {
		if (xhr.readyState == XMLHttpRequest.DONE) {
			output = xhr.responseText;
			output = JSON.parse(output);
			resp = output["status"];
			if(resp == 200 || resp == "success") {
				data = output["message"];
				l = data.length;
				for (var i=0; i<l; i++) {
					t = {
						instance: data[i]["ComponentName"],
						time: data[i]["ActiveTime"]
					};
					dataInstancesActiveTime.push(t);
				}
				console.log(dataInstancesActiveTime);				
				fetchDataInstancesActiveTimeWorkerRoles();
			}
			else {
				;
			}
		}
	}
	xhr.open('POST', '/api/instances-active-time');
	xhr.setRequestHeader('Content-type', 'application/json');
	// xhttp.setRequestHeader('Access-Control-Request-Headers', 'content-type');
	// xhttp.setRequestHeader('Access-Control-Request-Method', 'POST');
	req = {
		"tenantId": token["tenantId"],
		"componentType": "WebRole"
	}
	xhr.send(JSON.stringify(req));
}

function fetchDataInstancesActiveTimeWorkerRoles() {
	var xhr = new XMLHttpRequest();
	xhr.onreadystatechange = function () {
		if (xhr.readyState == XMLHttpRequest.DONE) {
			output = xhr.responseText;
			output = JSON.parse(output);
			resp = output["status"];
			if(resp == 200 || resp == "success") {
				data = output["message"];
				l = data.length;
				for (var i=0; i<l; i++) {
					t = {
						instance: data[i]["ComponentName"],
						time: data[i]["ActiveTime"]
					};
					dataInstancesActiveTime.push(t);
				}
				console.log(dataInstancesActiveTime);
				initGraph2();
			}
			else {
				;
			}
		}
	}
	xhr.open('POST', '/api/instances-active-time');
	xhr.setRequestHeader('Content-type', 'application/json');
	// xhttp.setRequestHeader('Access-Control-Request-Headers', 'content-type');
	// xhttp.setRequestHeader('Access-Control-Request-Method', 'POST');
	req = {
		"tenantId": token["tenantId"],
		"componentType": "WorkerRole"
	}
	xhr.send(JSON.stringify(req));
}

function fetchDataInstancesStatsWebRoles() {
	var xhr = new XMLHttpRequest();
	xhr.onreadystatechange = function () {
		if (xhr.readyState == XMLHttpRequest.DONE) {
			output = xhr.responseText;
			output = JSON.parse(output);
			resp = output["status"];
			if(resp == 200 || resp == "success") {
				data = output["message"];
				for (var componentName in data) {
					t = {
						instance: componentName,
						cpu: data[componentName]["cpu"],
						memory: data[componentName]["memory"]
					};
					dataInstancesStats.push(t);
				}
				console.log(dataInstancesStats);

				fetchDataInstancesStatsWorkerRoles();
			}
			else {
				;
			}
		}
	}
	xhr.open('POST', '/api/get-docker-stats');
	xhr.setRequestHeader('Content-type', 'application/json');
	// xhttp.setRequestHeader('Access-Control-Request-Headers', 'content-type');
	// xhttp.setRequestHeader('Access-Control-Request-Method', 'POST');
	req = {
		"tenantId": token["tenantId"],
		"componentType": "WebRole"
	}
	xhr.send(JSON.stringify(req));
}

function fetchDataInstancesStatsWorkerRoles() {
	var xhr = new XMLHttpRequest();
	xhr.onreadystatechange = function () {
		if (xhr.readyState == XMLHttpRequest.DONE) {
			output = xhr.responseText;
			output = JSON.parse(output);
			resp = output["status"];
			if(resp == 200 || resp == "success") {
				data = output["message"];
				l = data.length;
				for (var componentName in data) {
					t = {
						instance: componentName,
						cpu: data[componentName]["cpu"],
						memory: data[componentName]["memory"]
					};
					dataInstancesStats.push(t);
				}
				console.log(dataInstancesStats);
				initGraph3();					
			}
			else {
				;
			}
		}
	}
	xhr.open('POST', '/api/get-docker-stats');
	xhr.setRequestHeader('Content-type', 'application/json');
	// xhttp.setRequestHeader('Access-Control-Request-Headers', 'content-type');
	// xhttp.setRequestHeader('Access-Control-Request-Method', 'POST');
	req = {
		"tenantId": token["tenantId"],
		"componentType": "WorkerRole"
	}
	xhr.send(JSON.stringify(req));
}

function initGraph1() {
	now = new Date().getTime();
	graphUsersOverTime = Morris.Line({
		element: 'graph-users-over-time',
		xkey: 'timestamp',
		ykeys: ['value'],
		labels: ['Count'],
		hideHover: 'auto',
		lineColors: ['#26B99A', '#34495E', '#ACADAC', '#3498DB'],
		data: dataUsersOverTime,
		resize: true
	});
	setTimeout(function() {
		updateGraphUsersOverTime();
	}, 2000);
}

function initGraph2() {
	Morris.Bar({
		element: 'graph-instances-active-time',
		xkey: 'instance',
		ykeys: ['time'],
		labels: ['ActiveTime'],
		data: dataInstancesActiveTime,
		barRatio: 0.4,
		barColors: ['#26B99A', '#34495E', '#ACADAC', '#3498DB'],
		xLabelAngle: 35,
		hideHover: 'auto',
		resize: true
	  });
}

function initGraph3() {
	Morris.Bar({
		element: 'graph-instances-stats',
		xkey: 'instance',
		ykeys: ['cpu', 'memory'],
		labels: ['CPU', 'Memory'],
		data: dataInstancesStats,
		barRatio: 0.4,
		barColors: ['#26B99A', '#34495E', '#ACADAC', '#3498DB'],
		xLabelAngle: 35,
		hideHover: 'auto',
		resize: true
	  });
}

function updateGraphUsersOverTime() {
	var xhr = new XMLHttpRequest();
	xhr.onreadystatechange = function () {
		if (xhr.readyState == XMLHttpRequest.DONE) {
			output = xhr.responseText;
			output = JSON.parse(output);
			resp = output["status"];
			if(resp == 200 || resp == "success") {
				div = document.getElementById("num-active-users");
				div.innerHTML = output["message"];

				now = new Date().getTime();
				newData = {
					timestamp: now,
					value: output["message"]
				};
				dataUsersOverTime.push(newData);
				graphUsersOverTime.setData(dataUsersOverTime);
				setTimeout(function() {
					updateGraphUsersOverTime();
				}, 2000);
			}
			else {
				;
			}
		}
	}
	xhr.open('POST', '/api/active-users');
	xhr.setRequestHeader('Content-type', 'application/json');
	// xhttp.setRequestHeader('Access-Control-Request-Headers', 'content-type');
	// xhttp.setRequestHeader('Access-Control-Request-Method', 'POST');
	req = {
		"tenantId": token["tenantId"]
	}
	xhr.send(JSON.stringify(req));
}

$(document).ready(function() {
	fetchNumHits();
	fetchNumActiveUsers();
	fetchDataInstancesActiveTimeWebRoles();
	fetchDataInstancesStatsWebRoles();

	initGraph1();
});
