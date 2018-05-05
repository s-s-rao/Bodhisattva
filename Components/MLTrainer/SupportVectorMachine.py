import pickle
import numpy as np
import pandas as pd
from sklearn.preprocessing import LabelEncoder
from sklearn.svm import LinearSVC
from sklearn.model_selection import train_test_split

class SupportVectorMachine:
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
		
		# hyperparameters["probability"] = True
		hyperparameters["verbose"] = True		
		self.clf = LinearSVC(**hyperparameters)
		
		# TODO: FIX THIS. Automatically use the modelParameters dict to set the model's attributes
		if "support_vectors_" in modelParameters.keys():
			self.clf.support_vectors_ = modelParameters["support_vectors_"]

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