based on [twitchRSS](https://github.com/lzeke0/TwitchRSS)

# IMPORTANT: update to v1.1.2, previous verions contain a memory leak 

# TwitchToPodcastRSS

converts a twitch channel in a full blown podcast
<a label="example of it working with podcast addict" href="url"><img src="https://user-images.githubusercontent.com/4585690/129647659-b3bec66b-4cbb-408c-840c-9596f0c32dc2.jpg" align="left" height="400" ></a>
## Features:
- copletly converts the vods in a proper podcast RSS that can be listen directly inside the client (if they support audio only m3u8 playback, tested working on podcast addict), no need for the twitch app
- the descripion has a clickable image that opens the vod in the twitch app
- support for the new helix twitch API
- no trascoding or server side stream processing is done, the vods are not downloaded on the server, this also means that that the episodes are only avalible until they get deleted from twitch (2 weeks - 2 months in general)

## Known issues:
- first time you ask for a feed it will take up to a minute or two for the request to go through, this is due to technical limitations. since updates are generaly done in backgroud by the podcast clients this should not be a huge limitation, just give it time
- if the vod is unfinished due to the streamer still being online when your clients updates the duration told by the app will smaller than the finished stream duration

## Usage
when you host this just add /vod/channelName to your server path and an RSS will be generated

example: myserver.com/vod/channelname

just add the link to your podcast client

## install with docker
before doing anything be sure to get your SECRET and CLIENT ID from twitch
https://dev.twitch.tv/console

precompiled images are [here](https://hub.docker.com/r/madiele/twitch_to_podcast_rss/) for linux machines with arm64, amd64, arm/v7, i386 architectures

images for raspberry pis are included  


### use [docker-compose](https://docs.docker.com/compose/install/) with precompiled image (easiest)

`git clone https://github.com/madiele/TwitchToPodcastRSS.git`

`cd TwitchToPodcastRSS`

edit `docker-compose.yml` with your PORT, SECRET and CLIENT_ID

`nano TwitchToPodcastRSS`

save and

`sudo docker-compose up -d`

#### update

run this inside the folder with `docker-compose.yml` inside

`sudo docker-compose pull  && docker-compose up -d`

### pull the precompiled image from hub.docker.com
  
  `docker pull madiele/twitch_to_podcast_rss:latest`

edit with PORT,SECRET and CLIENT_ID

  `sudo docker run -d --restart always -p <PORT>:80 -e TWITCH_SECRET="<YOUR_SECRET>" -e TWITCH_CLIENT_ID="<YOUR_CLIENT_ID>" madiele/twitch_to_podcast_rss:latest`
  
  to update kill and delete the running container and run the same commands

### build it yourself (this will take a while)

`git clone https://github.com/madiele/TwitchToPodcastRSS.git`

`cd TwitchToPodcastRSS`

`docker build -t TwitchToPodcastRSS .`

edit with PORT,SECRET and CLIENT_ID

`sudo docker run -d --restart always -p <PORT>:80 -e TWITCH_SECRET="<YOUR_SECRET>" -e TWITCH_CLIENT_ID="<YOUR_CLIENT_ID>" TwitchToPodcastRSS`

### About
the original [twitchRSS](https://github.com/lzeke0/TwitchRSS) has been developed by László Zeke.
Later modified into [TwitchToPodcastRSS](https://github.com/madiele/TwitchToPodcastRSS) by Mattia Di Eleuterio

