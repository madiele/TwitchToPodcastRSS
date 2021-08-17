based on [twitchRSS](https://github.com/lzeke0/TwitchRSS)

# TwitchToPodcastRSS

converts a twitch channel in a full blown podcast

## Features:
- copletly converts the vods in a proper podcast RSS that can be listen directly inside the client (if they support audio only m3u8 playback, tested working on podcast addict), no need for the twitch app
- the descripion has a clickable image that opens the vod in the twitch app
- support for the new helix twitch API
- no trascoding or server side stream processing is done, the vods are not downloaded on the server, this also means that that the episodes are only avalible until they get deleted from twitch (2 weeks - 2 months in general)
- dropped support for live episodes: /vod/channel and /vodonly/channel do the same thing and will ignore live episodes


## Known issues:
- first time you ask for a feed it will take up to a minute for the request to go trhough, this is due to technical limitations 

when you host this just add /vod/channelName to your server path and an RSS will be generated

example: myserver.com/vod/channelname

## install with docker
before doing anything be sure to get your SECRET and CLIENT ID from twitch
https://dev.twitch.tv/console

precompiled images are here

https://hub.docker.com/r/madiele/twitch_to_podcast_rss/ (for linux arm64, amd64, arm/v7, i386)

images for raspberry pis are included  


### use [docker-compose](https://docs.docker.com/compose/install/) with precompiled image (esiest)

edit /docker-compose.yml with your PORT,SECRET and CLIENT_ID

`git clone https://github.com/madiele/TwitchToPodcastRSS.git`

`cd TwitchToPodcastRSS`

`sudo docker-compose up -d`

### pull the precompiled image from hub.docker.com
  
  `docker pull madiele/twitch_to_podcast_rss:latest`
  
  `sudo docker run -d --restart always -p <PORT>:80 -e TWITCH_SECRET="<YOUR_SECRET>" -e TWITCH_CLIENT_ID="<YOUR_CLIENT_ID>" madiele/twitch_to_podcast_rss:latest`

### build it yourself

then run those commands (change the stuff inside <_> with your data)

`git clone https://github.com/madiele/TwitchToPodcastRSS.git`

`cd TwitchToPodcastRSS`

`docker build -t TwitchToPodcastRSS .`

`sudo docker run -d --restart always -p <PORT>:80 -e TWITCH_SECRET="<YOUR_SECRET>" -e TWITCH_CLIENT_ID="<YOUR_CLIENT_ID>" TwitchToPodcastRSS`

# TwitchRSS original description:

## Twitch RSS Webapp for Google App Engine
This project is a very small web application for serving RSS feed for broadcasts
in Twitch. It fetches data from [Twitch API](https://dev.twitch.tv/docs) and caches in Memcache.
The engine is webapp2.

A running version can be tried out at:
~~https://twitchrss.appspot.com/vod/twitch~~ (hosts the original twitchRSS, not this version)

There is also a VOD only endpoint if you don't want to see ongoing streams which are known to break some readers:
~~https://twitchrss.appspot.com/vodonly/twitch~~ (hosts the original twitchRSS, not this version)

### Caching requests
This service caches requests from twitch for 10 minutes meaning that you will only get new answers once in
10 minutes. Please keep this in mind when polling the service.

### Deployment
First you should set your own Twitch API client ID in the app.yaml.
See how to deploy on [Google App Engine](https://cloud.google.com/appengine/docs/standard/python3).

### Other things
~~The project uses a slightly modified [Feedformatter](https://code.google.com/p/feedformatter/) to support
more tags and time zone in pubDate tag.~~ (moved to feedGenerator)

### About
The project has been developed by László Zeke.
Later modified by Mattia Di Eleuterio

