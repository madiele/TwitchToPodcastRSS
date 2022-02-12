FROM python:3.8.2-slim AS pipwheels
MAINTAINER Mattia Di Eleuterio <madile92@gmail.com>
RUN mkdir /pip_wheels
RUN apt-get update && apt-get install -y bash git g++ gcc libxml2 libpcre3-dev libxslt-dev python3-dev python3-lxml python3-pip
RUN pip3 install wheel
COPY ./TwitchRSS/requirements.txt .
RUN pip3 wheel -v $(cat requirements.txt | grep pycryptodome ) --wheel-dir=/pip_wheels
RUN apt-get install -y zlib1g-dev
RUN pip3 wheel -v $(cat requirements.txt | grep lxml ) --wheel-dir=/pip_wheels
RUN pip3 wheel -r ./requirements.txt --wheel-dir=/pip_wheels

FROM python:3.8.2-slim AS final-stage
COPY --from=pipwheels /pip_wheels /pip_wheels
RUN apt-get update && apt-get install -y libxslt-dev git ffmpeg && rm -rf /var/lib/apt/lists/*
COPY ./TwitchRSS/requirements.txt .
RUN pip3 install --no-index --find-links=/pip_wheels -r requirements.txt
COPY . /
WORKDIR /TwitchRSS
ENTRYPOINT ["/bin/bash", "./entrypoint.sh"]
