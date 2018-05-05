import pickle
import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder
from sklearn.neural_network import MLPClassifier
from sklearn.model_selection import train_test_split

class MultiLayerPerceptron:
	def __init__(self, features, labels, hyperparameters, modelParameters, trainTestSplit):
		if "random_state" in hyperparameters.keys():
			randomState = hyperparameters["random_state"]
		else:
			randomState = None
		featuresTrain, featuresTest, labelsTrain, labelsTest = train_test_split(features, labels, train_size=trainTestSplit, random_state=randomState)

		self.featuresTrain = featuresTrain
		self.labelsTrain = labelsTrain
		self.featuresTest = featuresTest
		self.labelsTest = labelsTest

		hyperparameters["verbose"] = True
		self.clf = MLPClassifier(**hyperparameters)
		
		# TODO: FIX THIS. Automatically use the modelParameters dict to set the model's attributes
		if "coefs_" in modelParameters.keys():
			self.clf.coefs_ = modelParameters["coefs_"]

	def train(self):
		self.clf.fit(self.featuresTrain, self.labelsTrain)
	
	def accuracy(self):
		return self.clf.score(self.featuresTest, self.labelsTest)
	
	""" 
	def predict(self, newData):
		return self.clf.predict(newData)
	 """

	def saveModelPickle(self, picklePath):
		with open(picklePath, "wb") as pkl:
			pickle.dump(self.clf, pkl)