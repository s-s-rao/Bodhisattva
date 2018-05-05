# !/bin/bash

# update aptitude
apt-get update

# install sshpass
apt-get install sshpass -y

# ssh into the remote machine
sshpass -p$2 ssh -o StrictHostKeyChecking=no root@$1 bash -c "'
	apt-get install git -y
	git clone https://github.com/s-s-rao/Bodhisattva.git
	cd ./Bodhisattva/
	sh ./Setup/Setup.sh
'"
exit