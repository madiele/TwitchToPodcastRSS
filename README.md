based on [twitchRSS](https://github.com/lzeke0/TwitchRSS)

# IMPORTANT: update to v1.1.2+, previous versions contain a memory leak 

# TwitchToPodcastRSS

converts a twitch channel in a full-blown podcast
<a label="example of it working with podcast addict" href="url"><img src="https://user-images.githubusercontent.com/4585690/129647659-b3bec66b-4cbb-408c-840c-9596f0c32dc2.jpg" align="left" height="400" ></a>
## Features:
- completely converts the vods in a proper podcast RSS that can be listened directly inside the client (if they support audio only m3u8 playback, [podcast addict](https://play.google.com/store/apps/details?id=com.bambuna.podcastaddict&hl=en_US&gl=US) is the only app I found that has support for it), no need for the twitch app
- the description has a clickable image that opens the vod in the twitch app
- support for the new helix twitch API
- no transcoding or server side stream processing is done, the vods are not downloaded on the server, this also means that the episodes are only available until they get deleted from twitch (2 weeks - 2 months in general)

## Known issues:
- first time you ask for a feed it will take up to a minute or two for the request to go through, this is due to technical limitations. since updates are generally done in background by the podcast clients this should not be a huge limitation, just give it time. if you only listen/watch inside the twitch app or website be sure to enable [links only mode](#only-links-mode) to make the feed generation much faster

## Usage
when you host this just add /vod/channelName to your server path and an RSS will be generated

example: `myserver.com/vod/channelname`

just add the link to your podcast client

### show currently streaming

unfinished streams are not included, but if you want them to just add `?include_streaming=True` to the feed URL

example: `myserver.com/vod/channelname?include_streaming=True`

### sorting

if you use a feed reader you can order the feed by any field suppored by twitch, the list of fields to sort by can be found [here](https://dev.twitch.tv/docs/api/reference#get-videos) in the response field section

by default it sorts by the published_at field

to enable sorting just add `sort_by=[key]` or/and `desc=True` to the URL

some examples:

to sort by views:

`myserver.com/vod/channelname?sort_by=view_count`

to sort by views descending:

`myserver.com/vod/channelname?sort_by=view_count&desc=true`

### only links mode

if you only listen to the episodes in the twitch app or website you can enable the `links_only=true` to skip the fetching of the audio stream, doing so will make the feed generation almost instant, so it's highly raccomanded to enable the option if you don't use the included audio feed

example: `myserver.com/vod/channelname?links_only=True`

### mixing options

to mix options just add `&` beetween them

example: `myserver.com/vod/channelname?sort_by=view_count&desc=true&links_only=true&include_streaming=True`

## install with docker
before doing anything be sure to get your SECRET and CLIENT ID from twitch
https://dev.twitch.tv/console

precompiled images are [here](https://hub.docker.com/r/madiele/twitch_to_podcast_rss/) for linux machines with arm64, amd64, arm/v7, i386 architectures

images for raspberry pis are included  


### use [docker-compose](https://docs.docker.com/compose/install/) with precompiled image (easiest)

`git clone https://github.com/madiele/TwitchToPodcastRSS.git`

`cd TwitchToPodcastRSS`

edit `docker-compose.yml` with your PORT, SECRET and CLIENT_ID

`nano docker-compose.yml`

save and

`sudo docker-compose up -d`

#### when you want to update:

run this inside the folder with `docker-compose.yml`

`sudo docker-compose pull && sudo docker-compose up -d`

then run this to delete the old version form your system (note: this will also delete any other unused image you have)

`sudo docker system prune`

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

