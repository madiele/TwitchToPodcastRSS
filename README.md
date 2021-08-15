based on [twitchRSS](https://github.com/lzeke0/TwitchRSS)

this is a modified version of twitchRSS that converts a twitch channel in a full blown podcast

## Diffrences from twitchRSS:
- copletly converts the vods in a proper podcast RSS that can be listen directly inside the client (if they support audio only m3u8 playback, tested working on podcast addict), no need for the twitch app
- added support for the new helix twitch API
- no trascoding or server side stream processing is done, the vods are not downloaded on the server, this also means that that the episodes are only avalible until they get deleted from twitch (2 weeks - 2 months in general)
- dropped support for live episodes: /vod/channel and /vodonly/channel do the same thing and will ignore live episodes


# TwitchRSS original description:

## Twitch RSS Webapp for Google App Engine
This project is a very small web application for serving RSS feed for broadcasts
in Twitch. It fetches data from [Twitch API](https://dev.twitch.tv/docs) and caches in Memcache.
The engine is webapp2.

A running version can be tried out at:
https://twitchrss.appspot.com/vod/twitch

There is also a VOD only endpoint if you don't want to see ongoing streams which are known to break some readers:
https://twitchrss.appspot.com/vodonly/twitch

### Caching requests
This service caches requests from twitch for 10 minutes meaning that you will only get new answers once in
10 minutes. Please keep this in mind when polling the service.

### Deployment
First you should set your own Twitch API client ID in the app.yaml.
See how to deploy on [Google App Engine](https://cloud.google.com/appengine/docs/standard/python3).

### Other things
The project uses a slightly modified [Feedformatter](https://code.google.com/p/feedformatter/) to support
more tags and time zone in pubDate tag.

### About
The project has been developed by László Zeke.
