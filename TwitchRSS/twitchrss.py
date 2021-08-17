
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
from streamlink import streams
import datetime
import gzip
import json
import logging
import pytz
import queue
import re
import subprocess
import time
import urllib



VOD_URL_TEMPLATE = 'https://api.twitch.tv/helix/videos?user_id=%s&type=all'
USERID_URL_TEMPLATE = 'https://api.twitch.tv/helix/users?login=%s'
VODCACHE_LIFETIME = 10 * 60
USERIDCACHE_LIFETIME = 24 * 60 * 60
VODURLSCACHE_LIFETIME = 24 * 60 * 60
CHANNEL_FILTER = re.compile("^[a-zA-Z0-9_]{2,25}$")
TWITCH_CLIENT_ID = environ.get("TWITCH_CLIENT_ID")
TWITCH_SECRET = environ.get("TWITCH_SECRET")
TWITCH_OAUTH_TOKEN = ""
TWITCH_OAUTH_EXPIRE_EPOCH = 0
logging.basicConfig(level=logging.DEBUG if environ.get('DEBUG') else logging.INFO)

if not TWITCH_CLIENT_ID:
    raise Exception("Twitch API client id env variable is not set.")
if not TWITCH_SECRET:
    raise Exception("Twitch API secret env variable not set.")


app = Flask(__name__)
streamUrl_queues = {}

def authorize():
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
            return
        except Exception as e:
            logging.warning("Fetch exception caught: %s" % e)
            retries += 1
    abort(503)



@cached(cache=TTLCache(maxsize=3000, ttl=VODURLSCACHE_LIFETIME))
def get_audiostream_url(vod_url):
    try:
        stream_url = streams(vod_url).get('audio').to_url() 
    except AttributeError as e:
        logging.error("streamlink has returned an error for the given vod: "+stream_url)
        logging.error(e)
    return stream_url

    
@app.route('/vod/<string:channel>', methods=['GET', 'HEAD'])
def vod(channel):
    if CHANNEL_FILTER.match(channel):
        return get_inner(channel)
    else:
        abort(404)


@app.route('/vodonly/<string:channel>', methods=['GET', 'HEAD'])
def vodonly(channel):
    if CHANNEL_FILTER.match(channel):
        return get_inner(channel, add_live=False)
    else:
        abort(404)

@app.route('/')
def index():
    return render_template('index.html')


def get_inner(channel, add_live=True):
    user_json = fetch_userid(channel)
    if not user_json:
        abort(404)

    (channel_display_name, channel_id, icon) = extract_userid(json.loads(user_json)['data'][0])

    channel_json = fetch_vods(channel_id)
    if not channel_json:
        abort(404)

    decoded_json = json.loads(channel_json)['data']
    rss_data = construct_rss(channel, decoded_json, channel_display_name, icon, add_live)
    headers = {'Content-Type': 'text/xml'}

    if 'gzip' in request.headers.get("Accept-Encoding", ''):
        headers['Content-Encoding'] = 'gzip'
        rss_data = gzip.compress(rss_data)

    return rss_data, headers


@cached(cache=TTLCache(maxsize=3000, ttl=USERIDCACHE_LIFETIME))
def fetch_userid(channel_name):
    return fetch_json(channel_name, USERID_URL_TEMPLATE)


@cached(cache=TTLCache(maxsize=500, ttl=VODCACHE_LIFETIME))
def fetch_vods(channel_id):
    return fetch_json(channel_id, VOD_URL_TEMPLATE)


@sleep_and_retry
@limits(calls=800, period=60)
def fetch_json(id, url_template):
    authorize()
    url = url_template % id
    headers = {
        'Authorization': 'Bearer '+TWITCH_OAUTH_TOKEN,
        'Client-Id': TWITCH_CLIENT_ID,
        'Accept-Encoding': 'gzip'
    }
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
    abort(503)


def extract_userid(user_info):
    # Get the first id in the list
    userid = user_info['id']
    username = user_info['display_name']
    icon = user_info['profile_image_url']
    if username and userid:
        return username, userid, icon
    else:
        logging.warning('Userid is not found in %s' % user_info)
        abort(404)


def construct_rss(channel_name, vods, display_name, icon, add_live=True):
    logging.debug("processing channel: " + channel_name)
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
    try:
        if vods:
            for vod in vods:
                logging.debug("processing vod:" + vod['id'])
                logging.debug(vod)
                item = feed.add_entry()
                #if vod["status"] == "recording":
                #    if not add_live:
                #        continue
                #    link = "http://www.twitch.tv/%s" % channel_name
                #    item.title("%s - LIVE" % vod['title'])
                #    item.category("live")
                #else:
                link = vod['url']
                item.title(vod['title'])
                #item.category(vod['type'])

                #prevent get_audiostream_url to be run concurrenty with the same paramenter

                global streamUrl_queues
                if not link in streamUrl_queues:
                    q = streamUrl_queues[link] = queue.Queue()
                else:
                    q = streamUrl_queues[link]
                q.put(link)
                q.get()

                item.enclosure(get_audiostream_url(link), type='audio/mpeg')

                q.task_done()
                q.join()
                # possible race condition, but should be fine after join()
                if (q.qsize == 0):
                    del streamUrl_queues[link]


                
                item.link(href=link, rel="related")
                thumb = vod['thumbnail_url'].replace("%{width}", "512").replace("%{height}","288")
                description = "<a href=\"%s\"><img src=\"%s\" /></a>" % (link, thumb)
                #if vod.get('game'):
                    #description += "<br/>" + vod['game']
                if vod['description']:
                    description += "<br/>" + vod['description']
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
        logging.warning('Issue with json: %s\nException: %s' % (vods, e))
        abort(404)

    logging.debug("all vods processed")
    return feed.rss_str()


# For debug
if __name__ == "__main__":
    app.run(host='127.0.0.1', port=8081, debug=True)
