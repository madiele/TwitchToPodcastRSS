"""
File: twitchrss.py
Author: Laszlo Zeke and Mattia Di Eleuterio
Github: https://github.com/madiele/TwitchToPodcastRSS
Description: webserver that converts a twitch channel into a podcast feed
"""

# Copyright 2020 Laszlo Zeke
# modifications: Copyright 2021 Mattia Di Eleuterio
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#

from cachetools import cached, TTLCache 
from feedgen.feed import FeedGenerator
from flask import abort, Flask, request, render_template
from os import environ
from ratelimit import limits, sleep_and_retry
from streamlink import Streamlink
from streamlink.exceptions import PluginError
from threading import Lock, RLock
from html import escape as HTMLescape
import datetime
import gzip
import json
import logging
import pytz
import re
import subprocess
import time
import urllib



VOD_URL_TEMPLATE = 'https://api.twitch.tv/helix/videos?user_id=%s&type=all'
USERID_URL_TEMPLATE = 'https://api.twitch.tv/helix/users?login=%s'
STREAMS_URL_TEMPLATE = 'https://api.twitch.tv/helix/streams?user_id=%s'
VODCACHE_LIFETIME = 10 * 60
USERIDCACHE_LIFETIME = 24 * 60 * 60
VODURLSCACHE_LIFETIME = 24 * 60 * 60
CHANNEL_FILTER = re.compile("^[a-zA-Z0-9_]{2,25}$")
TWITCH_CLIENT_ID = environ.get("TWITCH_CLIENT_ID")
TWITCH_SECRET = environ.get("TWITCH_SECRET")
TWITCH_OAUTH_TOKEN = ""
TWITCH_OAUTH_EXPIRE_EPOCH = 0
logging.basicConfig(
        format='%(asctime)s %(levelname)-8s %(message)s',
        level=logging.DEBUG if environ.get('DEBUG') else logging.INFO,
        datefmt='%Y-%m-%d %H:%M:%S'
        )


if not TWITCH_CLIENT_ID:
    raise Exception("Twitch API client id env variable is not set.")
if not TWITCH_SECRET:
    raise Exception("Twitch API secret env variable not set.")


app = Flask(__name__)
streamlink_session = Streamlink(options=None)
streamUrl_queues = {}
cache_locks = {
        'fetch_channel': Lock(),
        'fetch_vods': Lock(),
        'fetch_streams': Lock(),
        'get_audiostream_url': Lock(),
        }


def authorize():
    """updates the oauth token if expired."""

    global TWITCH_OAUTH_TOKEN
    global TWITCH_OAUTH_EXPIRE_EPOCH

    if (TWITCH_OAUTH_EXPIRE_EPOCH >= round(time.time())):
        return
    logging.debug("requesting a new oauth token")
    data = {
        'client_id': TWITCH_CLIENT_ID,
        'client_secret': TWITCH_SECRET,
        'grant_type': 'client_credentials',
    }
    url = 'https://id.twitch.tv/oauth2/token'
    request = urllib.request.Request(url, data=urllib.parse.urlencode(data).encode("utf-8"), method='POST')
    retries = 0
    while retries < 3:
        try:
            result = urllib.request.urlopen(request, timeout=3)
            r = json.loads(result.read().decode("utf-8"))
            TWITCH_OAUTH_TOKEN = r['access_token']
            TWITCH_OAUTH_EXPIRE_EPOCH = int(r['expires_in']) + round(time.time())
            logging.debug("oauth token aquired")
            logging.debug(TWITCH_CLIENT_ID)
            logging.debug(TWITCH_OAUTH_TOKEN)
            return
        except Exception as e:
            logging.warning("Fetch exception caught: %s" % e)
            retries += 1
    logging.error("could not get oauth token from twitch")
    abort(503)

class NoAudioStreamException(Exception):
    """NoAudioStreamException."""
    pass

@cached(cache=TTLCache(maxsize=3000, ttl=VODURLSCACHE_LIFETIME), lock=cache_locks['get_audiostream_url'])
def get_audiostream_url(vod_url):
    """finds the audio-strem URL for the given link and returns it.

    Args:
      vod_url: link to the vod

    Returns: the audio stream url

    
    """
    logging.debug("looking up audio url for " + vod_url)
    try:
        stream_url = streamlink_session.streams(vod_url).get('audio').to_url()
    except (AttributeError, PluginError) as e:
        logging.error("streamlink has returned an error:")
        logging.error(e)
        raise NoAudioStreamException
    return stream_url

@app.route('/vod/<string:channel>', methods=['GET', 'HEAD'])
def vod(channel):
    """process request to /vod/.

    Args:
      channel: 

    Returns: the http response

    
    """

    if CHANNEL_FILTER.match(channel):
        return process_channel(channel, request.args)
    else:
        abort(404)

@app.route('/vodonly/<string:channel>', methods=['GET', 'HEAD'])
def vodonly(channel):
    """process request to /vodonly/.

    Args:
      channel: 

    Returns: the http response

    
    """
    if CHANNEL_FILTER.match(channel):
        return process_channel(channel, request.args)
    else:
        abort(404)

@app.route('/')
def index():
    """process request to the root."""
    return render_template('index.html')


def process_channel(channel, request_args):
    """process the given channel.

    Args:
      channel: the channel string given in the request
      add_live: NOT YET REIMPLEMENTED (Default value = True)

    Returns: 
    (
        rss_data: the fully formed rss feed
        headers: the headers for the response
    )

    
    """
    include_streaming = True if request_args.get("include_streaming", "False") == "True" else False

    try:
        user_data = json.loads(fetch_channel(channel))['data'][0]
        channel_id = user_data['id']
        vods_data = json.loads(fetch_vods(channel_id))['data']
        streams_data = json.loads(fetch_streams(channel_id))['data']
    except KeyError as e:
        logging.error("could not fetch data for the given request")
        logging.error(e)
        abort(404)

    rss_data = construct_rss(user_data, vods_data, streams_data, include_streaming)
    headers = {'Content-Type': 'text/xml'}

    if 'gzip' in request.headers.get("Accept-Encoding", ''):
        headers['Content-Encoding'] = 'gzip'
        rss_data = gzip.compress(rss_data)

    return rss_data, headers


@cached(cache=TTLCache(maxsize=3000, ttl=USERIDCACHE_LIFETIME), lock=cache_locks['fetch_channel'])
def fetch_channel(channel_name):
    """fetches the JSON for the given channel username.

    Args:
      channel_name: the channel name

    Returns: the JSON formatted channel info

    
    """
    return fetch_json(channel_name, USERID_URL_TEMPLATE)


@cached(cache=TTLCache(maxsize=500, ttl=VODCACHE_LIFETIME), lock=cache_locks['fetch_vods'])
def fetch_vods(channel_id):
    """fetches the JSON for the given channel username.

    Args:
      channel_id: the unique identifier of the channel

    Returns: the JSON formatted vods list

    
    """
    return fetch_json(channel_id, VOD_URL_TEMPLATE)

@cached(cache=TTLCache(maxsize=500, ttl=VODCACHE_LIFETIME), lock=cache_locks['fetch_streams'])
def fetch_streams(user_id):
    return fetch_json(user_id, STREAMS_URL_TEMPLATE)

def getAuthHeaders(): 
    authorize()
    return {
        'Authorization': 'Bearer '+TWITCH_OAUTH_TOKEN,
        'Client-Id': TWITCH_CLIENT_ID,
        }


@sleep_and_retry
@limits(calls=800, period=60)
def fetch_json(id, url_template):
    """fetches a JSON from the given URL template and generic id.

    Args:
      id: the unique identifier of your request
      url_template: the template for the request where id will be replaced
    example: 'https://api.twitch.tv/helix/videos?user_id=%s&type=all'

    Returns: the JSON response for the request

    
    """
    url = url_template % id
    headers = getAuthHeaders()
    headers['Accept-Encoding'] = 'gzip'
    request = urllib.request.Request(url, headers=headers)
    retries = 0
    while retries < 3:
        try:
            result = urllib.request.urlopen(request, timeout=3)
            logging.debug('Fetch from twitch for %s with code %s' % (id, result.getcode()))
            if result.info().get('Content-Encoding') == 'gzip':
                logging.debug('Fetched gzip content')
                return gzip.decompress(result.read())
            return result.read()
        except Exception as e:
            logging.warning("Fetch exception caught: %s" % e)
            retries += 1
    logging.error("max retries reached, could not get resource, id: " + id)
    abort(503)


def construct_rss(user, vods, streams, includeStreams=False):
    """returns the RSS for the given inputs.

    Args:
      channel_name: username of the channel
      vods: parsed list of vods given by twitch
      display_name: the name channel
      icon: the icon url for the channel
      add_live: NOT REIMPLEMENTED YET (Default value = True)

    Returns: fully formatted RSS string

    
    """

    logging.debug("processing channel")
    try:
        channel_name = user['login']
        display_name = user['display_name']
        icon = user['profile_image_url']
        isStreaming = True if streams else False
    except KeyError as e:
        logging.error("error while processing user data")
        logging.error(e)
        abort(500)
    logging.debug("streaming=" + str(isStreaming))
    logging.debug("user data:")
    logging.debug(user)
    if isStreaming:
        logging.debug("streams data:")
        logging.debug(streams)

    
    feed = FeedGenerator()
    feed.load_extension('podcast')

    # Set the feed/channel level properties
    feed.image(url=icon)
    feed.id("https://github.com/madiele/TwitchToPodcastRSS")
    feed.title("%s's Twitch video RSS" % display_name)
    feed.link(href='https://twitchrss.appspot.com/', rel='self')
    feed.author(name="Twitch RSS Generated")
    feed.description("The RSS Feed of %s's videos on Twitch" % display_name)
    feed.podcast.itunes_author("Twitch RSS Generated")
    feed.podcast.itunes_complete(False)
    feed.podcast.itunes_explicit('no')
    feed.podcast.itunes_image(icon)
    feed.podcast.itunes_summary("The RSS Feed of %s's videos on Twitch" % display_name) 
    # Create an item
    if vods:
        for vod in vods:
            try:

                logging.debug("processing vod:" + vod['id'])
                logging.debug(vod)
                description = ""
                if isStreaming and vod['stream_id'] == streams[0]['id']:
                    if not includeStreams:
                        logging.debug("skipping incomplete vod")
                        continue
                    else:
                        description = "<p>warning: this stream is still going</p>"
                        thumb = "https://vod-secure.twitch.tv/_404/404_processing_320x180.png"
                else:
                    thumb = vod['thumbnail_url'].replace("%{width}", "512").replace("%{height}","288")
                item = feed.add_entry()
                link = vod['url']
                item.title(vod['title'])


                description += "<a href=\"%s\"><p>%s</p><img src=\"%s\" /></a>" % (link, HTMLescape(vod['title']), thumb)
                if vod['description']:
                    description += "<br/>" + vod['description']

                #prevent get_audiostream_url to be run concurrenty with the same paramenter
                #this way the next hit on get_audiostream_url will use the cache instead

                global streamUrl_queues
                if not link in streamUrl_queues:
                    q = streamUrl_queues[link] = {'lock': RLock(), 'count': 0}
                else:
                    q = streamUrl_queues[link]

                q['count'] = q['count'] + 1
                q['lock'].acquire()

                try:
                    stream_url = get_audiostream_url(link)
                except NoAudioStreamException as e:
                    description += "TwitchToPodcastRSS ERROR: could not fetch an audio stream for this vod,"
                    description += "try refreshing the RSS feed later"
                    stream_url = None



                q['count'] = q['count'] - 1
                if q['count'] == 0:
                    del streamUrl_queues[link]

                q['lock'].release()

                if (stream_url):
                    item.enclosure(stream_url, type='audio/mpeg')

                item.link(href=link, rel="related")
                item.description(description)
                date = datetime.datetime.strptime(vod['created_at'], '%Y-%m-%dT%H:%M:%SZ')
                item.podcast.itunes_duration(re.sub('[hm]',':', vod['duration']).replace('s',''))
                item.podcast.itunes_author(channel_name)
                if (thumb.endswith('.jpg') or thumb.endswith('.png')):
                    item.podcast.itunes_image(thumb)

                item.pubDate(pytz.utc.localize(date))
                item.updated(pytz.utc.localize(date))
                guid = vod['id']
                #if vod["status"] == "recording":  # To show a different news item when recording is over
                    #guid += "_live"
                item.guid(guid)
            except KeyError as e:
                logging.warning('Issue with json while processing vod: %s\n\nException: %s' % (vod, e))
                feed.remove_entry(item)

    logging.debug("all vods processed")
    return feed.rss_str()


# For debug
if __name__ == "__main__":
    app.run(host='127.0.0.1', port=8081, debug=True)
