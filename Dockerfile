FROM python:3.8.2-slim
MAINTAINER Mattia Di Eleuterio <madile92@gmail.com>

RUN apt-get update && apt-get install -y bash git g++ gcc libxml2 libpcre3-dev libxslt-dev python3-dev python3-lxml python3-pip && apt-get clean
RUN apt-get install python3-pycryptodome
RUN pip3 install -v pycryptodome
RUN apt-get -y install python-lxml 
RUN apt-get -y install zlib1g-dev
#this will take a loooong time
RUN pip3 install -v lxml
ADD . /
WORKDIR /TwitchRSS
RUN pip3 install --disable-pip-version-check wheel && pip3 install --disable-pip-version-check -r requirements.txt && pip3 cache purge 
ENTRYPOINT ["gunicorn", "-b",  ":80", "-k", "gthread", "twitchrss:app"]
