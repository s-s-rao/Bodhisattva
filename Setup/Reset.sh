pkill -9 python3
docker stop $(docker ps -aq)
docker rm $(docker ps -aq)
docker volume prune -f
docker network rm RainMakerNetwork
docker rmi $(docker images -q)
docker rmi $(docker images -f "dangling=true" -q)
docker ps -a
docker network ls
docker image ls