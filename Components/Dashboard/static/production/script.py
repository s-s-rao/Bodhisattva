import os
import glob

path = '/templates/'

filename = glob.glob('*.html')

for i in filename:
	f = open(i).read()
	f.replace('<link', '<link href= "/static/vendors/bootstrap/dist/css/bootstrap.min.css" rel="stylesheet">')
	f.replace('src="/images', 'src="/static/production/images/')

	# with open(i,'r') as f:
	# 	contents = f.readlines()
	# 	for line in contents.split("\n"):



	# 	for n,content in enumerate(contents):
	# 		content = content.strip()
	# 		words = content.split(' ')
	# 		for k,j in enumerate(words):
	# 			if( j == '<link'):
	# 				contents[n] = "<link href= \"/static/vendors/bootstrap/dist/css/bootstrap.min.css\" rel=\"stylesheet\">"
	# 			if( j == '<img'):
	# 				w = words[k+1]
	# 				w_list = w.split('/')
	# 				w_list[0] = "src=\"/static/images/"
	# 				w1 = w_list[0]+w_list[1]	
	# 				content = content.replace(w,w1)
	# 				contents[n] = content
	# 			#elif(content.find('src=')):
	# 			#	content = content.replace("src=\"images","src=\"/static/images")
	# 			#	contents[n] = content

	# 		with open(i,'w')as f:
	# 			for content in contents:
	# 				#print(content)
	# 				f.write(content)		
	# 			f.close()
				


				
