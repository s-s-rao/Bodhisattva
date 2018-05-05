import urllib
import pandas as pd
import urllib.request
from socket import timeout

chunkSize = 10 ** 6

""" 
def getData(urls):
	data = pd.read_csv(url[0])

	# CANNOT SEND PANDAS DATAFRAME IN JSON HTTP REQUEST
	return data.to_dict()
 """


def saveDataToVolume(url, hostVolumePath):
	# TODO: use chunking for large files. chunksize argument used to read file chunk by chunk, and returns TextFileReader object

	# save the data to volume
	fileName = url.split("/")[-1]
	filePath = hostVolumePath + "data/" + fileName

	try:
		response = urllib.request.urlretrieve(url, filePath)
	except (urllib.error.HTTPError, urllib.error.URLError) as error:
		s = "Data not retrieved because {} for URL: {}".format(error, url)
		res = {"status": 404, "message": s}
		return res
	except timeout:
		s = "Socket timed out for URL: {}".format(url)
		res = {"status": 404, "message": s}
		return res
	
	res = {"status": 200, "fileName": fileName}
	return res


"""
def serveData(DataObjectReference, returnType):
	# outputType can be "batch" or "streaming"
		# if batch, return output - but costly, as MLTrainer has to wait for all data to be returned before 
		# if streaming, yield output - tricky to implement
		pass
"""