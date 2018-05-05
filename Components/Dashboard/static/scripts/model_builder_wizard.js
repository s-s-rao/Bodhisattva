myProgressBar = null;
predInputData = null;
buttonNext = null;
numPredictors = 1;
finalNumPredictors = 1;


rawDeploymentTemplate = {};

baseModelNames = [
	"MLPClassifier",
	"SVMClassifier",
	"KMeansClustering"
];
baseModelName = baseModelNames[0];
baseModelId = 1;
modelName = "";
modelDescription = "";

dataSourceType = "URL";
dataSourceURL = "";
dataSourceExisting = "";
trainTestSplit = 80;
isDataSchemaSet = false;
dataSchema = [];

availableHyperparameters = {
	"mlp": {
		"hidden_layer_sizes": "list",
		"activation": "string",
		"solver": "string",
		"learning_rate_init": "number",
		"max_iter": "number",
		"shuffle": "boolean",
		"random_state": "number",
		"momentum": "number"
	},
	"svm": {},
	"kmeans": {}
};
hyperparameters = [];

availableModelParameters = {
	"mlp": {
		"coefs_": "list"
	},
	"svm": {},
	"kmeans": {}
};
modelParameters = [];

trainingDeploymentParameters = {};

filledDeploymentTemplate = {};
filledDeploymentTemplate["modelDetails"] = {};
filledDeploymentTemplate["modelDetails"]["modelName"] = {};
filledDeploymentTemplate["modelDetails"]["modelDescription"] = {};
filledDeploymentTemplate["modelDetails"]["baseModelName"] = {};
filledDeploymentTemplate["modelDetails"]["baseModelId"] = {};
filledDeploymentTemplate["trainingDataDetails"] = {};
filledDeploymentTemplate["trainingDataDetails"]["dataSourceType"] = {};
filledDeploymentTemplate["trainingDataDetails"]["dataSourceURL"] = {};
filledDeploymentTemplate["trainingDataDetails"]["dataSourceExisting"] = {};
filledDeploymentTemplate["trainingDataDetails"]["trainTestSplit"] = {};
filledDeploymentTemplate["trainingDataDetails"]["dataSchema"] = {};
filledDeploymentTemplate["hyperparameters"] = {};
filledDeploymentTemplate["modelParameters"] = {};
filledDeploymentTemplate["trainingDeploymentParameters"] = {};
filledDeploymentTemplate["trainingDeploymentParameters"]["parallelizationMethod"] = {};

modelId = null;
modelAccuracy = 0.0;

myProgressBar = null;
myProgressBarTimeout = null;
isProgressBarFinished = false;
isModelTrained = false;

prepareModelFailureMessage = "Model preparation failed. ";
trainModelFailureMessage = "Model training failed. ";
deployPredictorsFailureMessage = "Failed to deploy predictors. ";

availableUntrainedModels = [
	"mlp",
	"svm",
	"kmeans"
];
modelShortName = availableUntrainedModels[0];



(function(){
	function onChange(event) {
		var reader = new FileReader();
		reader.onload = onReaderLoad;
		reader.readAsText(event.target.files[0]);
	}

	function onReaderLoad(event){
		// console.log(event.target.result);
		rawDataSchema = JSON.parse(event.target.result);
		// console.log(rawDataSchema);
		newDataSchema = [];
		for (var columnNum in rawDataSchema) {
			column = rawDataSchema[columnNum];
			// console.log(column);
			newColumn = {};
			newColumn["value"] = {};
			newColumn["value"]["columnName"] = {};
			newColumn["value"]["columnName"]["value"] = column["columnName"];
			newColumn["value"]["dataType"] = {};
			newColumn["value"]["dataType"]["value"] = column["dataType"];
			newColumn["value"]["isLabelColumn"] = {};
			newColumn["value"]["isLabelColumn"]["value"] = false;
			if ("isLabelColumn" in column) {
				newColumn["value"]["isLabelColumn"]["value"] = column["isLabelColumn"];
			}
			newColumn["value"]["ignoreColumn"] = {};
			newColumn["value"]["ignoreColumn"]["value"] = false;
			if ("ignoreColumn" in column) {
				newColumn["value"]["ignoreColumn"]["value"] = column["ignoreColumn"];
			}
			newDataSchema.push(newColumn);
		}
		dataSchema = newDataSchema;
		isDataSchemaSet = true;
		// console.log(dataSchema);
	}

	document.getElementById('data-schema-file').addEventListener('change', onChange);
}());

function refreshProgressBar() {
	console.log("refreshProgressBar");
	myProgressBarTimeout = null;
	myProgressBar.setAttribute("data-transitiongoal", "0");
	myProgressBar.setAttribute("aria-valuenow", "0");
	myProgressBar.style.width = "0%";
	isProgressBarFinished = false;
	
	progressBarHolder = document.getElementById("progress-bar-holder");
	console.log("before - ", progressBarHolder);
	// progressBarHolder.removeChild(progressBarHolder.childNodes[0]);
	/* while (progressBarHolder.hasChildNodes()) {
		progressBarHolder.removeChild(progressBarHolder.lastChild);
	} */
	/* progBar = document.getElementById("my-progress-bar");
	progBar.parentNode.removeChild(progBar); */
	// $("#progress-bar-holder").empty();
	progressBarHolder.innerHTML = "";
	progressBarHolder = document.getElementById("progress-bar-holder");	
	console.log("after - ", progressBarHolder);	
	progressBarHolder.style.visibility = "hidden";

	newProgressBar = document.createElement("div");
	newProgressBar.setAttribute("id", "my-progress-bar");
	newProgressBar.setAttribute("class", "progress-bar progress-bar-info");
	newProgressBar.setAttribute("data-transitiongoal", "0");
	newProgressBar.setAttribute("aria-valuenow", "0");
	newProgressBar.style.width = "0%";

	progressBarHolder.appendChild(newProgressBar);
	progressBarHolder.style.visibility = "visible";

	myProgressBar = document.getElementById("my-progress-bar");
}

function finishProgressBar() {
	console.log("finishProgressBar");
	myProgressBar.setAttribute("data-transitiongoal", "100");
	myProgressBar.setAttribute("aria-valuenow", "100");
	myProgressBar.style.width = "100%";
	isProgressBarFinished = true;
}

function makeProgress() {
	// console.log("makeProgress");
	if (myProgressBar.getAttribute("data-transitiongoal") == 100) {
		isProgressBarFinished = true;
		console.log("progress done");
		return;
	}
	else {
		a = myProgressBar.getAttribute("data-transitiongoal");
		aa = parseInt(a);
		aa = aa + 1;
		myProgressBar.setAttribute("data-transitiongoal", aa.toString());
		myProgressBar.setAttribute("aria-valuenow", aa.toString());
		myProgressBar.style.width = aa.toString() + "%";

		/* if(isModelTrained) {
			finishProgressBar();
			return;
		} */

		myProgressBarTimeout = setTimeout(makeProgress, 50);
	}
}

function startProgressBar() {
	console.log("startProgressBar");
	makeProgress();
}

function prepareModel() {
	console.log("prepareModel");

	if (! buildDeploymentTemplate()) {
		return;
	}

	trainModelButton = document.getElementById("train-model-button");
	trainModelButton.disabled = true;

	isModelTrained = false;

	accuracyMeterDiv = document.getElementById('accuracy-meter-div');
	accuracyMeterDiv.style.visibility = "hidden";

	myProgressBar = document.getElementById("my-progress-bar");
	refreshProgressBar();

	$(".prepmodel-alert").each(function() {
		$(this).css("display", "none");
	});

	alertBox = document.getElementById("prepmodel-alert-dummy");
	alertBox.style.display = "inline-block";

	/* alertBox = document.getElementById("prepmodel-alert-failure");
	alertBox.style.display = "none"; */

	buttonNext = $(".buttonNext:first");
	buttonNext.addClass("buttonDisabled");
	// console.log(buttonNext.attr("class"));

	

	var xhr = new XMLHttpRequest();
	xhr.onreadystatechange = function () {
		if (xhr.readyState == XMLHttpRequest.DONE) {
			output = xhr.responseText;
			output = JSON.parse(output);
			// console.log(output);
			resp = output["status"];
			if(resp == 200 || resp == "success") {
				modelId = output["modelId"];
				// console.log("modelId: " + modelId.toString());
				
				$(".prepmodel-alert").each(function() {
					$(this).css("display", "none");
				});

				/* alertBox = document.getElementById("prepmodel-alert-dummy");
				alertBox.style.display = "none"; */

				alertBox = document.getElementById("prepmodel-alert-success");
				alertBox.style.display = "inline-block";

				trainModel();
			}
			else {
				trainModelButton = document.getElementById("train-model-button");
				trainModelButton.disabled = false;
				
				$(".prepmodel-alert").each(function() {
					$(this).css("display", "none");
				});

				/* alertBox = document.getElementById("prepmodel-alert-dummy");
				alertBox.style.display = "none"; */

				alertBox = document.getElementById("prepmodel-alert-failure");
				alertBox.innerHTML = prepareModelFailureMessage + "<strong>" + output["message"] + "</strong>";
				alertBox.style.display = "inline-block";
			}
		}
	}
	xhr.open('POST', '/api/prepare-model');
	xhr.setRequestHeader('Content-type', 'application/json');
	// xhttp.setRequestHeader('Access-Control-Request-Headers', 'content-type');
	// xhttp.setRequestHeader('Access-Control-Request-Method', 'POST');
	req = {
		"token": token,
		"filledDeploymentTemplate": filledDeploymentTemplate
	}
	xhr.send(JSON.stringify(req));
}

function trainModel() {
	console.log("trainModel");

	$(".trainmodel-alert").each(function() {
		$(this).css("display", "none");
	});

	alertBox = document.getElementById("trainmodel-alert-dummy");
	alertBox.style.display = "inline-block";

	/* alertBox = document.getElementById("trainmodel-alert-failure");
	alertBox.style.display = "none"; */

	startProgressBar();

	var xhr = new XMLHttpRequest();
	xhr.onreadystatechange = function () {
		if (xhr.readyState == XMLHttpRequest.DONE) {
			output = xhr.responseText;
			output = JSON.parse(output);
			resp = output["status"];
			if(resp == 200 || resp == "success") {
				modelAccuracy = output["accuracy"];
				// console.log("modelAccuracy: " + modelAccuracy.toString());
				isModelTrained = true;

				clearTimeout(myProgressBarTimeout);
				finishProgressBar();

				$(".trainmodel-alert").each(function() {
					$(this).css("display", "none");
				});

				/* alertBox = document.getElementById("trainmodel-alert-dummy");
				alertBox.style.display = "none"; */
				
				alertBox = document.getElementById("trainmodel-alert-success");
				alertBox.style.display = "inline-block";
				
				generateAccuracyMeter();

				buttonNext.removeClass("buttonDisabled");
				// console.log(buttonNext.attr("class"));

				trainModelButton = document.getElementById("train-model-button");
				trainModelButton.disabled = false;
			}
			else {
				trainModelButton = document.getElementById("train-model-button");
				trainModelButton.disabled = false;

				$(".trainmodel-alert").each(function() {
					$(this).css("display", "none");
				});

				/* alertBox = document.getElementById("trainmodel-alert-dummy");
				alertBox.style.display = "none"; */

				alertBox = document.getElementById("trainmodel-alert-failure");
				alertBox.innerHTML = trainModelFailureMessage + "<strong>" + output["message"] + "</strong>";
				alertBox.style.display = "inline-block";
			}
		}
	}
	xhr.open('POST', '/api/train-model');
	xhr.setRequestHeader('Content-type', 'application/json');
	// xhttp.setRequestHeader('Access-Control-Request-Headers', 'content-type');
	// xhttp.setRequestHeader('Access-Control-Request-Method', 'POST');
	req = {
		"token": token,
		"modelId": modelId
	}
	xhr.send(JSON.stringify(req));
}

function deployPredictors(event) {
	console.log("deployPredictors");
	event.preventDefault();

	if (numPredictors == 0) {
		alert("You cannot deploy 0 predictors!");
		return;
	}

	$(".deploypred-alert").each(function() {
		$(this).css("display", "none");
	});

	loading = document.getElementById("deploy-predictors-loading");
	loading.style.visibility = "visible";

	if (!isModelTrained) {
		alertBox = document.getElementById("deploypred-alert-warning");
		alertBox.style.display = "inline-block";
		return;
	}

	/* alertBox = document.getElementById("deploypred-alert-warning");
	alertBox.style.display = "none"; */

	finalNumPredictors = numPredictors;

	var xhr = new XMLHttpRequest();
	xhr.onreadystatechange = function () {
		if (xhr.readyState == XMLHttpRequest.DONE) {
			output = xhr.responseText;
			output = JSON.parse(output);
			resp = output["status"];
			if(resp == 200 || resp == "success") {
				predCount = document.getElementById("predictor-count");
				predCount.innerHTML = finalNumPredictors.toString();

				deployPredsButton = document.getElementById("deploy-predictors-button");
				deployPredsButton.disabled = true;

				$(".deploypred-alert").each(function() {
					$(this).css("display", "none");
				});

				/* alertBox = document.getElementById("deploypred-alert-failure");
				alertBox.style.display = "none"; */
				alertBox = document.getElementById("deploypred-alert-success");
				alertBox.style.display = "inline-block";
			}
			else {
				$(".deploypred-alert").each(function() {
					$(this).css("display", "none");
				});
				alertBox = document.getElementById("deploypred-alert-failure");
				alertBox.innerHTML = deployPredictorsFailureMessage + "<strong>" + output["message"] + "</strong>";
				alertBox.style.display = "inline-block";
			}
			loading.style.visibility = "hidden";
		}
	}
	xhr.open('POST', '/api/start-predictors');
	xhr.setRequestHeader('Content-type', 'application/json');
	// xhttp.setRequestHeader('Access-Control-Request-Headers', 'content-type');
	// xhttp.setRequestHeader('Access-Control-Request-Method', 'POST');
	req = {
		"token": token,
		"modelId": modelId,
		"numPredictors": finalNumPredictors
	}
	xhr.send(JSON.stringify(req));
}

$("#base-model").change(function() {
	baseModels = document.getElementById("base-model");
	selected = baseModels.selectedIndex;
	modelShortName = availableUntrainedModels[selected];
	// alert(modelShortName);
	$(".hp-form-inner").each(function() {
		// console.log("none");
		$(this).css("display", "none");
	});
	hpInnerForm = document.getElementById("hp-form-inner-" + modelShortName);
	hpInnerForm.style.display = "block";
	// console.log("block");
	$(".mp-form-inner").each(function() {
		// console.log("none");
		$(this).css("display", "none");
	});
	mpInnerForm = document.getElementById("mp-form-inner-" + modelShortName);
	mpInnerForm.style.display = "block";
	// console.log("block");
	// selected = $("#base-model option:selected")[0];
	// alert(availableUntrainedModels[selected]);
	// hp = document.getElementById("hp-form");
	// hp.innerHTML = `{% include "hp_` + modelShortName + `.html" %}`;
	// mp = document.getElementById("mp-form");
	// mp.innerHTML = `{% include "mp_` + modelShortName + `.html" %}`;
	baseModelId = selected + 1;
	baseModelName = baseModelNames[selected];

	// updateHyperparameters();
	// updateModelParameters();
});

function updateHyperparameters() {
	hps = [];
	selector = "#hp-"+modelShortName+" .hp";
	// console.log(selector);
	hpInputs = document.querySelectorAll(selector);
	l = hpInputs.length;
	for (var i=0; i<l; i++) {
		// console.log(i);
		hpName = hpInputs[i].id;
		hpType = availableHyperparameters[modelShortName][hpName];
		// console.log(hpName);
		hpValue = null;
		if (hpType == "boolean") {
			hpValue = hpInputs[i].checked;
		}
		else {
			hpValue = hpInputs[i].value;
			if (hpType == "number") {
				if (hpValue == "") {
					hpValue = 0;
				}
				else {
					hpValue = parseFloat(hpValue);
				}
			}
			else if (hpType == "list") {
				if (hpValue == "") {
					continue;
				}
				hpValue = hpValue.replace("[", "").replace("]", "");
				hpValue = "["+hpValue.trim()+"]";
				reg = /\[\d+(\s*\,\s*\d+\s*)*\]/i;
				hpValue = JSON.parse(hpValue);
			}
		}
		hp = {
			"hyperparameterNameDev": hpName,
			"value": hpValue
		}
		hps.push(hp);
	}
	// console.log(hps);
	hyperparameters = hps;
}

function updateModelParameters() {
	mps = [];
	mps1 = {};

	selector = "#mp-"+modelShortName+" .mp";
	// console.log(selector);
	mpInputs = document.querySelectorAll(selector);
	l = mpInputs.length;
	for (var i=0; i<l; i++) {
		// console.log(i);
		mpName = mpInputs[i].id;
		mpType = availableModelParameters[modelShortName][mpName];
		// console.log(mpName);
		mpValue = null;
		if (mpType == "boolean") {
			mpValue = mpInputs[i].checked;
		}
		else {
			mpValue = mpInputs[i].value;
			if (mpType == "number") {
				if (mpValue == "") {
					mpValue = 0;
				}
				else {
					mpValue = parseFloat(mpValue);
				}
			}
			else if (mpType == "list") {
				if (mpValue == "") {
					continue;
				}
				mpValue = mpValue.replace("[", "").replace("]", "");
				mpValue = "["+mpValue.trim()+"]";
				reg = /\[\d+(\s*\,\s*\d+\s*)*\]/i;
				mpValue = JSON.parse(mpValue);
			}
		}
		mps1[mpName] = mpValue;
	}
	// console.log(mps1);

	selector = "#mp-"+modelShortName+" .mp-def";
	// console.log(selector);
	mpInputs = document.querySelectorAll(selector);
	l = mpInputs.length;
	for (var i=0; i<l; i++) {
		// console.log(i);
		mpName = mpInputs[i].id.replace("-def", "");
		mpType = availableModelParameters[modelShortName][mpName];
		
		mpValue = mpInputs[i].checked;
		if (mpValue) {
			delete mps1[mpName];
		}
	}
	// console.log(mps1);

	l = mps1.length;
	for (var mpName in mps1) {
		mpValue = mps1[mpName];
		mp = {
			"hyperparameterNameDev": mpName,
			"value": mpValue
		}
		mps.push(mp);
	}
	// console.log(mps);
	modelParameters = mps;
}

function buildDeploymentTemplate() {
	modelNameInput = document.getElementById("model-name");
	modelDescriptionInput = document.getElementById("model-description");
	modelName = modelNameInput.value;
	modelDescription = modelDescriptionInput.value;
	if (modelName == "") {
		alert("Please enter a model name!");
		return false;
	}
	if (modelDescription == "") {
		alert("Please enter some description for the model!");
		return false;
	}
	filledDeploymentTemplate["modelDetails"]["modelName"]["value"] = modelName;
	filledDeploymentTemplate["modelDetails"]["modelDescription"]["value"] = modelDescription;
	filledDeploymentTemplate["modelDetails"]["baseModelName"]["value"] = baseModelName;
	filledDeploymentTemplate["modelDetails"]["baseModelId"]["value"] = baseModelId;

	dataSourceTypeInput = document.getElementById("data-source-type");
	dataSourceType = dataSourceTypeInput.value;
	filledDeploymentTemplate["trainingDataDetails"]["dataSourceType"]["value"] = dataSourceType;
	dataSourceURLInput = document.getElementById("data-source-url");
	dataSourceURL = dataSourceURLInput.value;
	if (dataSourceURL == "") {
		alert("Please enter a URL to fetch training data from!");
		return false;
	}
	filledDeploymentTemplate["trainingDataDetails"]["dataSourceURL"]["value"] = dataSourceURL;
	// TODO: add option and all necessary code
	// filledDeploymentTemplate["trainingDataDetails"]["dataSourceExisting"] = {};

	filledDeploymentTemplate["trainingDataDetails"]["trainTestSplit"]["value"] = trainTestSplit;
	if (! isDataSchemaSet) {
		alert("Please upload the schema file for the training data!");
		return false;
	}
	filledDeploymentTemplate["trainingDataDetails"]["dataSchema"]["value"] = dataSchema;

	updateHyperparameters();
	filledDeploymentTemplate["hyperparameters"]["value"] = hyperparameters;

	updateModelParameters();
	filledDeploymentTemplate["modelParameters"]["value"] = modelParameters;

	// TODO: change after implementing training parallelization
	filledDeploymentTemplate["trainingDeploymentParameters"]["parallelizationMethod"]["value"] = "none";

	console.log(filledDeploymentTemplate);

	return true;
}

$("#train-test-split").knob({
	change : function (value) {
		// console.log("change : " + Math.round(value));
		trainTestSplit = Math.round(value);
	}, // this is the change
});

$("#num-predictors").knob({
	change : function (value) {
		// console.log("change : " + Math.round(value));
		numPredictors = Math.round(value);
	}, // this is the change
});

function myPrediction() {
	predInputData = document.getElementById("inputData");
	predInput = predInputData.value;

	var xhr = new XMLHttpRequest();
	xhr.onreadystatechange = function () {
		if (xhr.readyState == XMLHttpRequest.DONE) {
			predOutputElement = document.getElementById('outputData');
			output = xhr.responseText;
			output = JSON.parse(output);
			predOutputElement.value = '[' + output['predictionOutput'] + ']';
			// alert(xhr.responseText);
		}
	}
	xhr.open('POST', '/predict', false);
	xhr.setRequestHeader('Content-type', 'text/plain');
	// xhttp.setRequestHeader('Access-Control-Request-Headers', 'content-type');
	// xhttp.setRequestHeader('Access-Control-Request-Method', 'POST');
	xhr.send(predInput);
}

function generateAccuracyMeter() {
	console.log("generateAccuracyMeter");
	accuracyMeterDiv = document.getElementById("accuracy-meter-div")
	accuracyMeterDiv.style.visibility = "visible";

	var chart_gauge_settings = {
		lines: 12,
		angle: 0,
		lineWidth: 0.4,
		pointer: {
			length: 0.75,
			strokeWidth: 0.042,
			color: '#1D212A'
		},
		limitMax: 'true',
		colorStart: '#5bc0de',
		colorStop: '#5bc0de',
		strokeColor: '#F0F3F3',
		generateGradient: true
	};
	var meter = document.getElementById('accuracy-meter');
	var accuracyMeter = new Gauge(meter).setOptions(chart_gauge_settings);
	accuracyMeter.maxValue = 10000;
	accuracyMeter.animationSpeed = 1;
	accuracyMeter.set(modelAccuracy*100);
	accuracyMeter.setTextField(document.getElementById("accuracy-meter-gauge-text"));
	accuracyText = document.getElementById("accuracy-meter-gauge-text");
	setTimeout(() => {
		setAccuracyText(accuracyText);
	}, 1000);
}

function validateStep(stepNumber) {
	// TODO: finish this. Different validations for different steps.
	return true;
}

function makeSmartWizard() {
	console.log("makeSmartWizard");
	
	$('#model-wizard').smartWizard({
		// enableAllSteps: true,
		// hideButtonsOnDisabled: true,
		showStepURLhash: false,
		theme: 'arrows',
		transitionEffect: 'fade',
		keyNavigation: false
	});

	$("#model-wizard").on("leaveStep", function(e, anchorObject, stepNumber, stepDirection) {
		// e.preventDefault();
		v = validateStep(stepNumber);
		console.log("validation for step" + stepNumber + ": " + v);
		return v;
	});

	$('.buttonNext').addClass('btn btn-success');
	$('.buttonPrevious').addClass('btn btn-primary');
	$('.buttonFinish').addClass('btn btn-default');
	
};

function setAccuracyText(accuracyText) {
	x = Math.round(modelAccuracy*100)/100;
	accuracyText.innerHTML = x.toString();
}

/* // iCheck
function initCheckbox() {
	if ($("input.flat")[0]) {
        $(document).ready(function () {
            $('input.flat').iCheck({
                checkboxClass: 'icheckbox_flat-green',
                radioClass: 'iradio_flat-green'
            });
        });
    }
} */

$(document).ready(function() {
	makeSmartWizard();
	// initCheckbox();
	// updateHyperparameters();
	// updateModelParameters();
});
