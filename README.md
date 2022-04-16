based on [twitchRSS](https://github.com/lzeke0/TwitchRSS)

# TwitchToPodcastRSS

converts a twitch channel in a full-blown podcast
<a label="example of it working with podcast addict" href="url"><img src="https://user-images.githubusercontent.com/4585690/129647659-b3bec66b-4cbb-408c-840c-9596f0c32dc2.jpg" align="left" height="400" ></a>
## Features:
- completely converts the vods in a proper podcast RSS that can be listened directly inside the client (you can even disable trascoding if they support audio only m3u8 playback, [podcast addict](https://play.google.com/store/apps/details?id=com.bambuna.podcastaddict&hl=en_US&gl=US) is the only app I found that has support for it), no need for the twitch app
- the description has a clickable image that opens the vod in the twitch app
- the vods are not downloaded on the server, this means that the episodes are only available until they get deleted from twitch (2 weeks - 2 months in general, depends on the creator settings)
- vods are transcoded to mp3 192k on the fly by default, tested to be working flawlessly even on a raspberry pi 3.

## Known issues:
- when transcoding seeking to the last minute or so can be buggy, I have no idea why, help is welcome
- to improve performance you can only have one ongoing transcoding of the same vod on the same client at once
- when transcoding seeking around too fast can be buggy
- when playing transcoded vod's mp3 it's possible to hear audio skipping 1-2 second in time every once in a while, this is caused by the connection dropping when downloading, and due to a technical limitation can't really be fixed (twitch gives a variable bitrate stream with seek data in seconds, but the clients wants a fixed bitrate stream with seek data in bytes, when converting some rounding errors cause the audio to glitch)
- (only if transcoding is disabled) first time you ask for a feed it will take up to a minute or two for the request to go through, this is due to technical limitations. since updates are generally done in background by the podcast clients this should not be a huge limitation, just give it time. if you only listen/watch inside the twitch app or website be sure to enable [links only mode](#only-links-mode) to make the feed generation much faster
- (only if transcoding is disabled) downloading only works with transcoding enabled (unless the client supports m3u8 download, which is rare)

## Donations
this is a passion project, and mostly made for myself, but if you want to gift me a pizza margherita feel free!

[!["Buy Me A Coffee"](https://www.buymeacoffee.com/assets/img/custom_images/orange_img.png)](https://www.buymeacoffee.com/madiele)

## Usage
when you host this just add /vod/channelName to your server path and an RSS will be generated

example: `myserver.com/vod/channelname`

just add the link to your podcast client

### transcoding
to enable transcoding just add `?transcode=true` to your url

example: `myserver.com/vod/channelname?transcode=True`

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
(in the file you will find also optional parameters like sub_folder for use with reverse proxies, define a unique server name, and so on)

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

## install without docker
since this is a flask app most methods of deployment listed [here](https://flask.palletsprojects.com/en/2.0.x/deploying/index.html) should work too

### About
the original [twitchRSS](https://github.com/lzeke0/TwitchRSS) has been developed by László Zeke.
Later modified into [TwitchToPodcastRSS](https://github.com/madiele/TwitchToPodcastRSS) by Mattia Di Eleuterio

