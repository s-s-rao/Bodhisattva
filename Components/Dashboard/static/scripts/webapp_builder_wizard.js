webroleCount = 1;
workerroleCount = 1;
finalWebroleCount = 1;
finalWorkerroleCount = 1;

isWebappCreated = false;
areWebrolesDeployed = false;
areWorkerrolesDeployed = false;
isWebappDeployed = false;

createWebappFailureMessage = "Web app initialization failed."
deployWebrolesFailureMessage = "Failed to deploy web roles for your web app."
deployWorkerrolesFailureMessage = "Failed to deploy worker roles for your web app."


function createWebapp(event) {
	console.log("createWebapp");
	event.preventDefault();

	$(".create-webapp-alert").each(function() {
		$(this).css("display", "none");
	});

	webappRepoURLDiv = document.getElementById("git-repo-url");
	webappRepoURL = webappRepoURLDiv.value;

	var xhr = new XMLHttpRequest();
	xhr.onreadystatechange = function () {
		if (xhr.readyState == XMLHttpRequest.DONE) {
			output = xhr.responseText;
			output = JSON.parse(output);
			resp = output["status"];
			if(resp == 200 || resp == "success") {
				isWebappCreated = true;

				createWebappButton = document.getElementById("create-webapp-button");
				createWebappButton.disabled = true;

				$(".create-webapp-alert").each(function() {
					$(this).css("display", "none");
				});

				alertBox = document.getElementById("create-webapp-alert-success");
				alertBox.style.display = "inline-block";

				deployWebappButton = document.getElementById("deploy-webapp-button");
				deployWebappButton.style.visibility = "visible";
			}
			else {
				$(".create-webapp-alert").each(function() {
					$(this).css("display", "none");
				});
				alertBox = document.getElementById("create-webapp-alert-failure");
				alertBox.innerHTML = createWebappFailureMessage + "<strong>" + output["message"] + "</strong>";
				alertBox.style.display = "inline-block";
			}
		}
	}
	xhr.open('POST', '/api/create-webapp');
	xhr.setRequestHeader('Content-type', 'application/json');
	// xhttp.setRequestHeader('Access-Control-Request-Headers', 'content-type');
	// xhttp.setRequestHeader('Access-Control-Request-Method', 'POST');
	req = {
		"token": token,
		"url": webappRepoURL
	}
	xhr.send(JSON.stringify(req));
}

function deployWebroles(event) {
	console.log("deployWebroles");

	$(".deploy-webroles-alert").each(function() {
		$(this).css("display", "none");
	});

	if (!isWebappCreated) {
		alertBox = document.getElementById("deploy-webroles-alert-warning");
		alertBox.style.display = "inline-block";
		return;
	}

	finalWebroleCount = webroleCount;

	var xhr = new XMLHttpRequest();
	xhr.onreadystatechange = function () {
		if (xhr.readyState == XMLHttpRequest.DONE) {
			output = xhr.responseText;
			output = JSON.parse(output);
			resp = output["status"];
			if(resp == 200 || resp == "success") {
				webCount = document.getElementById("webrole-count");
				webCount.innerHTML = finalWebroleCount.toString();

				areWebrolesDeployed = true;
				if(areWorkerrolesDeployed) {
					isWebappDeployed = true;
					deployWebappButton = document.getElementById("deploy-webapp-button");
					deployWebappButton.disabled = true;
				}

				$(".deploy-webroles-alert").each(function() {
					$(this).css("display", "none");
				});

				alertBox = document.getElementById("deploy-webroles-alert-success");
				alertBox.style.display = "inline-block";
			}
			else {
				$(".deploy-webroles-alert").each(function() {
					$(this).css("display", "none");
				});
				alertBox = document.getElementById("deploy-webroles-alert-failure");
				alertBox.innerHTML = deployWebrolesFailureMessage + "<strong>" + output["message"] + "</strong>";
				alertBox.style.display = "inline-block";
			}
		}
	}
	xhr.open('POST', '/api/deploy-webapp-component');
	xhr.setRequestHeader('Content-type', 'application/json');
	// xhttp.setRequestHeader('Access-Control-Request-Headers', 'content-type');
	// xhttp.setRequestHeader('Access-Control-Request-Method', 'POST');
	req = {
		"token": token,
		"componentType": "WebRole",
		"numOfComponents": finalWebroleCount
	}
	xhr.send(JSON.stringify(req));
}

function deployWorkerroles(event) {
	console.log("deployWorkerroles");

	$(".deploy-workerroles-alert").each(function() {
		$(this).css("display", "none");
	});

	if (!isWebappCreated) {
		alertBox = document.getElementById("deploy-workerroles-alert-warning");
		alertBox.style.display = "inline-block";
		return;
	}

	finalWorkerroleCount = workerroleCount;

	var xhr = new XMLHttpRequest();
	xhr.onreadystatechange = function () {
		if (xhr.readyState == XMLHttpRequest.DONE) {
			output = xhr.responseText;
			output = JSON.parse(output);
			resp = output["status"];
			if(resp == 200 || resp == "success") {
				workerCount = document.getElementById("workerrole-count");
				workerCount.innerHTML = finalWorkerroleCount.toString();

				areWorkerrolesDeployed = true;
				if(areWebrolesDeployed) {
					isWebappDeployed = true;
					deployWebappButton = document.getElementById("deploy-webapp-button");
					deployWebappButton.disabled = true;
				}

				$(".deploy-workerroles-alert").each(function() {
					$(this).css("display", "none");
				});

				alertBox = document.getElementById("deploy-workerroles-alert-success");
				alertBox.style.display = "inline-block";
			}
			else {
				$(".deploy-workerroles-alert").each(function() {
					$(this).css("display", "none");
				});
				alertBox = document.getElementById("deploy-workerroles-alert-failure");
				alertBox.innerHTML = deployWorkerrolesFailureMessage + "<strong>" + output["message"] + "</strong>";
				alertBox.style.display = "inline-block";
			}
		}
	}
	xhr.open('POST', '/api/deploy-webapp-component');
	xhr.setRequestHeader('Content-type', 'application/json');
	// xhttp.setRequestHeader('Access-Control-Request-Headers', 'content-type');
	// xhttp.setRequestHeader('Access-Control-Request-Method', 'POST');
	req = {
		"token": token,
		"componentType": "WorkerRole",
		"numOfComponents": finalWorkerroleCount
	}
	xhr.send(JSON.stringify(req));
}

function deployWebapp(event) {
	console.log("deployWebapp");
	event.preventDefault();

	deployWebappButton = document.getElementById("deploy-webapp-button");
	deployWebappButton.disabled = true;

	deployWebroles();
	deployWorkerroles();
}

$("#num-webroles").knob({
	change : function (value) {
		// console.log("change : " + Math.round(value));
		webroleCount = Math.round(value);
	}, // this is the change
});

$("#num-workerroles").knob({
	change : function (value) {
		// console.log("change : " + Math.round(value));
		workerroleCount = Math.round(value);
	}, // this is the change
});



function validateStep(stepNumber) {
	// TODO: finish this. Different validations for different steps.
	return true;
}

function makeSmartWizard() {
	console.log("makeSmartWizard");
	
	$('#webapp-wizard').smartWizard({
		// enableAllSteps: true,
		// hideButtonsOnDisabled: true,
		showStepURLhash: false,
		theme: 'arrows',
		transitionEffect: 'fade'
	});

	$("#webapp-wizard").on("leaveStep", function(e, anchorObject, stepNumber, stepDirection) {
		// e.preventDefault();
		v = validateStep(stepNumber);
		console.log("validation for step" + stepNumber + ": " + v);
		return v;
	});

	$('.buttonNext').addClass('btn btn-success');
	$('.buttonPrevious').addClass('btn btn-primary');
	$('.buttonFinish').addClass('btn btn-default');
	
};

$(document).ready(function() {
	makeSmartWizard();
});