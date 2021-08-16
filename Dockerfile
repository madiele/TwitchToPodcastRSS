FROM python:3.8.2-slim
MAINTAINER Mattia Di Eleuterio <madile92@gmail.com>

RUN apt-get update && apt-get install -y bash git g++ gcc libxml2 libpcre3-dev libxslt-dev python3-dev python3-pip && apt-get clean
ADD . /
WORKDIR /TwitchRSS
RUN pip3 install --disable-pip-version-check wheel && pip3 install --disable-pip-version-check --ignore-installed -r requirements.txt
ENTRYPOINT ["gunicorn", "-b",  ":80", "-k", "gthread", "twitchrss:app"]
