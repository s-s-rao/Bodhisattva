# !/bin/bash

# update apt
sudo apt-get -y update

# install docker
sudo apt-get -y remove docker docker-engine docker.io
sudo apt-get -y update
sudo apt-get -y install apt-transport-https ca-certificates curl software-properties-common
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo apt-key add -
sudo apt-key fingerprint 0EBFCD88
sudo add-apt-repository "deb [arch=amd64] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable"
sudo apt-get -y update
sudo apt-get -y install docker-ce

# Reset previous install
sudo sh ./Setup/Reset.sh

# initialize
sudo apt-get -y install python3-pip
sudo pip3 install --upgrade pip
sudo apt-get -y install mysql-client
pip3 install pymysql
python3 ./Setup/Init.py

# run DockerUI container to view, monitor, create and delete Docker components through a web-based UI (on port 8383)
docker run -d --name=DockerUI -p 8383:9000 --privileged -v /var/run/docker.sock:/var/run/docker.sock uifd/ui-for-docker

# display docker network
docker network ls

echo "\n"

# display created containers
docker ps -a


echo "\n\nListening..."
# # start ML Controller
# pip3 install -r ./Components/MLController/Requirements.txt
# python3 ./Components/MLController/MLControllerApp.py

# start CloudController
# pip3 install -r ./Components/CloudController/Requirements.txt
# python3 ./Components/CloudController/CloudControllerApp.py