FROM ubuntu:latest
RUN apt-get update -y; exit 0;
RUN apt-get install -y mysql-client
RUN apt-get install -y python3 python3-pip
RUN pip3 install --upgrade pip
COPY . /app
WORKDIR /app
RUN pip3 install -r /app/Requirements.txt
ENTRYPOINT ["python3"]
CMD ["MLTrainerApp.py"]