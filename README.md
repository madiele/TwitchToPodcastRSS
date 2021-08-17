based on [twitchRSS](https://github.com/lzeke0/TwitchRSS)

# TwitchToPodcastRSS

converts a twitch channel in a full blown podcast

## Features:
- copletly converts the vods in a proper podcast RSS that can be listen directly inside the client (if they support audio only m3u8 playback, tested working on podcast addict), no need for the twitch app
- the descripion has a clickable image that opens the vod in the twitch app
- support for the new helix twitch API
- no trascoding or server side stream processing is done, the vods are not downloaded on the server, this also means that that the episodes are only avalible until they get deleted from twitch (2 weeks - 2 months in general)


## Known issues:
- first time you ask for a feed it will take up to a minute or two for the request to go trhough, this is due to technical limitations. since updates are generaly done in backgroud by the podcast clients this should not be a huge limitation, just give it time

## Usage
when you host this just add /vod/channelName to your server path and an RSS will be generated

example: myserver.com/vod/channelname

## install with docker
before doing anything be sure to get your SECRET and CLIENT ID from twitch
https://dev.twitch.tv/console

precompiled images are here

https://hub.docker.com/r/madiele/twitch_to_podcast_rss/ (for linux arm64, amd64, arm/v7, i386)

images for raspberry pis are included  


### use [docker-compose](https://docs.docker.com/compose/install/) with precompiled image (easiest)

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

### About
the original [twitchRSS](https://github.com/lzeke0/TwitchRSS) has been developed by László Zeke.
Later modified into [TwitchToPodcastRSS](https://github.com/madiele/TwitchToPodcastRSS) by Mattia Di Eleuterio

