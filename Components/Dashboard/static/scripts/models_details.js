

function fetchModelDetails() {
	console.log("fetchModelDetails");

	var xhr = new XMLHttpRequest();
	xhr.onreadystatechange = function () {
		if (xhr.readyState == XMLHttpRequest.DONE) {
			output = xhr.responseText;
			output = JSON.parse(output);
			resp = output["status"];
			if(resp == 200 || resp == "success") {
				customTrainedTable = document.getElementById("table-body-customtrained");
				stripeOptions = ["even", "odd"];
				stripe = 0;
				output["modelDetails"]["tenanttrained"].forEach(element => {
					tr = document.createElement("tr");
					tr.setAttribute("class", stripeOptions[stripe] + " pointer");
					td1 = document.createElement("td");
					td1.setAttribute("class", " ");
					td1.innerHTML = element["ModelName"];
					td2 = document.createElement("td");
					td2.setAttribute("class", " ");
					td2.innerHTML = element["Description"];
					td3 = document.createElement("td");
					td3.setAttribute("class", " last");
					td3.innerHTML = "<a href='#'>View predictors</a>";
					tr.appendChild(td1);
					tr.appendChild(td2);
					tr.appendChild(td3);
					customTrainedTable.appendChild(tr);
					stripe += 1;
				});

				pretrainedTable = document.getElementById("table-body-pretrained");
				stripeOptions = ["even", "odd"];
				stripe = 0;
				output["modelDetails"]["pretrained"].forEach(element => {
					tr = document.createElement("tr");
					tr.setAttribute("class", stripeOptions[stripe] + " pointer");
					td1 = document.createElement("td");
					td1.setAttribute("class", " ");
					td1.innerHTML = element["ModelName"];
					td2 = document.createElement("td");
					td2.setAttribute("class", " ");
					td2.innerHTML = element["Description"];
					td3 = document.createElement("td");
					td3.setAttribute("class", " last");
					td3.innerHTML = "<a href='#'>Deploy predictors</a>";
					tr.appendChild(td1);
					tr.appendChild(td2);
					tr.appendChild(td3);
					pretrainedTable.appendChild(tr);
					stripe += 1;
				});

				untrainedTable = document.getElementById("table-body-untrained");
				stripeOptions = ["even", "odd"];
				stripe = 0;
				output["modelDetails"]["untrained"].forEach(element => {
					tr = document.createElement("tr");
					tr.setAttribute("class", stripeOptions[stripe] + " pointer");
					td1 = document.createElement("td");
					td1.setAttribute("class", " ");
					td1.innerHTML = element["ModelName"];
					td2 = document.createElement("td");
					td2.setAttribute("class", " ");
					td2.innerHTML = element["Description"];
					td3 = document.createElement("td");
					td3.setAttribute("class", " last");
					td3.innerHTML = "<a href='#'>Train model</a>";
					tr.appendChild(td1);
					tr.appendChild(td2);
					tr.appendChild(td3);
					untrainedTable.appendChild(tr);
					stripe += 1;
				});

				numAlgosDiv = document.getElementById("num-ml-algos");
				numAlgosDiv.innerHTML = output["modelDetails"]["untrained"].length;
			}
			else {
				;
			}
		}
	}
	xhr.open('POST', '/api/fetch-models');
	xhr.setRequestHeader('Content-type', 'application/json');
	// xhttp.setRequestHeader('Access-Control-Request-Headers', 'content-type');
	// xhttp.setRequestHeader('Access-Control-Request-Method', 'POST');
	req = {
		"token": token
	}
	xhr.send(JSON.stringify(req));
}

function fetchNumPretrainedDeployed() {
	var xhr = new XMLHttpRequest();
	xhr.onreadystatechange = function () {
		if (xhr.readyState == XMLHttpRequest.DONE) {
			output = xhr.responseText;
			output = JSON.parse(output);
			resp = output["status"];
			if(resp == 200 || resp == "success") {
				div = document.getElementById("num-deployed-pretrained");
				div.innerHTML = output["message"];
			}
			else {
				;
			}
		}
	}
	xhr.open('POST', '/api/pre-trained-models-by-tenant');
	xhr.setRequestHeader('Content-type', 'application/json');
	// xhttp.setRequestHeader('Access-Control-Request-Headers', 'content-type');
	// xhttp.setRequestHeader('Access-Control-Request-Method', 'POST');
	req = {
		"tenantId": token["tenantId"]
	}
	xhr.send(JSON.stringify(req));
}

function fetchNumTenantTrainedDeployed() {
	var xhr = new XMLHttpRequest();
	xhr.onreadystatechange = function () {
		if (xhr.readyState == XMLHttpRequest.DONE) {
			output = xhr.responseText;
			output = JSON.parse(output);
			resp = output["status"];
			if(resp == 200 || resp == "success") {
				div = document.getElementById("num-deployed-customtrained");
				div.innerHTML = output["message"];
			}
			else {
				;
			}
		}
	}
	xhr.open('POST', '/api/tenant-trained-models-deployed');
	xhr.setRequestHeader('Content-type', 'application/json');
	// xhttp.setRequestHeader('Access-Control-Request-Headers', 'content-type');
	// xhttp.setRequestHeader('Access-Control-Request-Method', 'POST');
	req = {
		"tenantId": token["tenantId"]
	}
	xhr.send(JSON.stringify(req));
}

function fetchNumTenantTrainedUndeployed() {
	var xhr = new XMLHttpRequest();
	xhr.onreadystatechange = function () {
		if (xhr.readyState == XMLHttpRequest.DONE) {
			output = xhr.responseText;
			output = JSON.parse(output);
			resp = output["status"];
			if(resp == 200 || resp == "success") {
				div = document.getElementById("num-undeployed-customtrained");
				div.innerHTML = output["message"];
			}
			else {
				;
			}
		}
	}
	xhr.open('POST', '/api/tenant-trained-models-not-deployed');
	xhr.setRequestHeader('Content-type', 'application/json');
	// xhttp.setRequestHeader('Access-Control-Request-Headers', 'content-type');
	// xhttp.setRequestHeader('Access-Control-Request-Method', 'POST');
	req = {
		"tenantId": token["tenantId"]
	}
	xhr.send(JSON.stringify(req));
}

$(document).ready(function() {
	fetchModelDetails();
	fetchNumPretrainedDeployed();
	fetchNumTenantTrainedDeployed();
	fetchNumTenantTrainedUndeployed();
});
