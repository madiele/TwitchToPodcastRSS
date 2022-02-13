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

from collections import OrderedDict
from html import escape as html_escape
from os import environ
from threading import Lock, RLock
from dateutil.parser import parse as parse_date
import subprocess
import datetime
import gzip
import json
import logging
import re
import time
import urllib
import random

import pytz
import m3u8
from cachetools import cached, TTLCache
from feedgen.feed import FeedGenerator
from flask import abort, Flask, request, render_template, stream_with_context, Response, url_for
from git import Repo
from ratelimit import limits, sleep_and_retry
from streamlink import Streamlink
from streamlink.exceptions import PluginError

app = Flask(__name__)

VOD_URL_TEMPLATE = 'https://api.twitch.tv/helix/videos?sort=time&user_id=%s&type=all'
USERID_URL_TEMPLATE = 'https://api.twitch.tv/helix/users?login=%s'
STREAMS_URL_TEMPLATE = 'https://api.twitch.tv/helix/streams?user_id=%s'
VODCACHE_LIFETIME = 10 * 60
USERIDCACHE_LIFETIME = 24 * 60 * 60
VODURLSCACHE_LIFETIME = 24 * 60 * 60
CHECK_UPDATE_INTERVAL = 24 * 60 * 60
CHANNEL_FILTER = re.compile("^[a-zA-Z0-9_]{2,25}$")
TWITCH_CLIENT_ID = environ.get("TWITCH_CLIENT_ID")
TWITCH_SECRET = environ.get("TWITCH_SECRET")
TWITCH_OAUTH_TOKEN = ""
TWITCH_OAUTH_EXPIRE_EPOCH = 0
GITHUB_REPO = 'madiele/TwitchToPodcastRSS'
GIT_ROOT = '..'
GIT_REPO = Repo(GIT_ROOT)
TRANSCODE = False
TRANSCODE_BITRATE = 128000
TRANSCODE_SECONDS_BUFFER = 120
TRANSCODE_BANDWITH_kbps = 500
if environ.get('TRANSCODE') and environ.get('TRANSCODE').lower() == 'true':
    TRANSCODE = True
if environ.get('TRANSCODE_BITRATE'):
    TRANSCODE_BITRATE = int(environ.get('TRANSCODE_BITRATE'))
if environ.get('TRANSCODE_SECONDS_BUFFER'):
    TRANSCODE_SECONDS_BUFFER = int(environ.get('TRANSCODE_SECONDS_BUFFER'))
if environ.get('TRANSCODE_BANDWITH_kbps'):
    TRANSCODE_BANDWITH_kbps = float(environ.get('TRANSCODE_BANDWITH_kbps'))

if environ.get('SERVER_NAME'):
    app.config['SERVER_NAME'] = environ.get('SERVER_NAME')
if environ.get('SUB_FOLDER'):
    app.config['APPLICATION_ROOT'] = environ.get('SUB_FOLDER')

# finds what's the lastes tagged release is locally
TTP_VERSION = sorted(GIT_REPO.tags, key=lambda t: t.commit.committed_datetime)[-1].name

logging.basicConfig(
    format='%(asctime)s %(levelname)-8s %(message)s',
    level=logging.DEBUG if environ.get('DEBUG') else logging.INFO,
    datefmt='%Y-%m-%d %H:%M:%S'
)

if not TWITCH_CLIENT_ID:
    raise Exception("Twitch API client id env variable is not set.")
if not TWITCH_SECRET:
    raise Exception("Twitch API secret env variable not set.")

streamlink_session = Streamlink(options=None)
streamUrl_queues = {}
cache_locks = {
    'fetch_channel': Lock(),
    'fetch_vods': Lock(),
    'fetch_streams': Lock(),
    'get_audiostream_url': Lock(),
    'check_for_updates': Lock(),
}


# noinspection PyUnresolvedReferences
@cached(cache=TTLCache(maxsize=1, ttl=CHECK_UPDATE_INTERVAL), lock=cache_locks['check_for_updates'])
def new_release_available():
    """check to see if there are new releases on the git repo.

        Returns: True if there are, False otherwise
    """
    url = 'https://api.github.com/repos/%s/releases/latest' % GITHUB_REPO
    request = urllib.request.Request(url, method='GET')
    try:
        result = urllib.request.urlopen(request, timeout=3)
        data = json.loads(result.read().decode('utf-8'))
        remote_version = data['tag_name']
        if remote_version == TTP_VERSION:
            return False
        else:
            logging.warning("new version avalible:" + TTP_VERSION + " -> " + remote_version)
            return True
    except urllib.error.HTTPError as e:
        logging.warning('could not check for updates, reason:')
        logging.warning(e)
        logging.warning(e.read().decode())
    return False


def authorize():
    """updates the oauth token if expired."""

    global TWITCH_OAUTH_TOKEN
    global TWITCH_OAUTH_EXPIRE_EPOCH

    if TWITCH_OAUTH_EXPIRE_EPOCH >= round(time.time()):
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
        except urllib.error.HTTPError as e:
            logging.warning("Fetch exception caught: %s" % e)
            logging.warning(e.read().decode())
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
    tries = 0;
    max_tries = 3;
    while tries < max_tries:
        tries = tries + 1
        try:
            vod = streamlink_session.streams(vod_url)

            if 'audio' not in vod:
                #TODO: cache the error in some way to prevent calling streamlink on the same vod
                #      so to reduce wasted api calls
                logging.debug("the selected vod does not have an audio stream")
                raise NoAudioStreamException("no audio stream available")

            stream_url = vod.get('audio').to_url()
            return stream_url

        except PluginError as e:
            logging.error("streamlink has returned an error for url " + str(vod_url) + ":")
            logging.error(e)
            if tries >= max_tries:
                raise NoAudioStreamException("could not process the audio stream")

    raise NoAudioStreamException("could not get the audio stream for uknown reason")

active_transcodes = {}
next_transcode_id = random.randint(0, 999999)
@app.route('/transcode/<string:vod_id>.mp3', methods=['GET'])
def transcode(vod_id):
    """given a vod_id it generates an mp3 version of it

        Returns: the ffmpeg transcoded output to the client
    """
    response = Response(mimetype = "audio/mpeg")

    session_id = None
    stream_url = 'https://www.twitch.tv/videos/' + vod_id
    start_time = 0
    requested_bytes = 0
    try:
        m3u8_url = get_audiostream_url(stream_url)
    except NoAudioStreamException as e:
        logging.info("requester stream could not be found: " + stream_url)
        response.status_code = 404
        return response

    def get_duration_m3u8(line, lineno, data, state):
        if line.startswith('#EXT-X-TWITCH-TOTAL-SECS'):
            custom_tag = line.split(':')
            data['duration'] = custom_tag[1].strip()

    playlist = m3u8.load(m3u8_url, custom_tags_parser=get_duration_m3u8)

    bitrate = TRANSCODE_BITRATE
    duration = int(round(float(playlist.data['duration'])))
    length = int(round(bitrate/8 * duration))


    if request.cookies.get("session_id") is None:
        global next_transcode_id
        session_id = next_transcode_id
        response.set_cookie("session_id", str(session_id))
        next_transcode_id += 1
    else:
        session_id = int(request.cookies.get('session_id'))


    if 'Range' in request.headers:
        requested_bytes = int(request.headers.get("Range").split("=")[1].split("-")[0])
        logging.debug("requested bytes: " + str(requested_bytes))
        start_time = round((int(requested_bytes) / length) * duration)
        if start_time > duration or requested_bytes > length:
            logging.debug("requested range is longer than the media")
            response.status_code = 416
            return response


    response.accept_ranges = 'bytes'
    response.content_range = "bytes " + str(requested_bytes) + "-" + str(length-1) + "/" +str(length)
    if start_time > 0:
        response.status_code = 206
        response.content_length = str(length - requested_bytes)
        logging.debug("content range header: " + str(response.content_range))
    else:
        response.status_code = 200
        response.content_length = str(length)

    logging.debug("stream_url: " + stream_url)
    logging.debug("m3u8_url: " + m3u8_url)
    logging.debug("start_time: " + str(start_time))
    logging.debug("bitrate: " + str(bitrate))
    logging.debug("duration in seconds: " + str(duration))
    logging.debug("byte length: " + str(length))

    def get_transcode_id():
        return str(session_id) + "_" + str(vod_id)

    def generate():
        buff = []
        stream_url = 'https://www.twitch.tv/videos/' + vod_id
        if get_transcode_id() in active_transcodes:
            logging.debug("killing old trascoding process: " + get_transcode_id())
            active_transcodes[get_transcode_id()].kill()
            active_transcodes.pop(get_transcode_id())


        ffmpeg_command = ["ffmpeg", "-ss", str(start_time), "-i", m3u8_url, "-acodec" ,"libmp3lame", "-ab", str(bitrate/1000)+ "k", "-f", "mp3", "-bufsize", str(TRANSCODE_SECONDS_BUFFER * bitrate), "-maxrate", str(TRANSCODE_BANDWITH_kbps) + "k", "pipe:stdout"]
        logging.debug(re.sub(r"[\[|,|\]|\']", "", str(ffmpeg_command)))
        process = subprocess.Popen(ffmpeg_command, stdout = subprocess.PIPE, stderr = subprocess.PIPE, bufsize = -1)
        active_transcodes[get_transcode_id()] = process
        logging.debug("active transcodes: " + str(active_transcodes.keys()))

        try:
            while True:
                line = process.stdout.read(1024)
                buff.append(line)

                yield buff.pop(0)

                process.poll()
                if isinstance(process.returncode, int):
                    if process.returncode > 0:
                        logging.error("ffmpeg error")
                        logging.error(process.stderr.read())
                    if get_transcode_id() in active_transcodes:
                        active_transcodes.pop(get_transcode_id())
                    break
        finally:
            process.kill()
            if get_transcode_id() in active_transcodes:
                active_transcodes.pop(get_transcode_id())
                logging.debug("active_transcodes: " + str(active_transcodes.keys()))

    response.response = stream_with_context(generate())

    if start_time == 0:
        logging.info('requested transcoding for:' + stream_url)

    return response

@app.route('/vod/<string:channel>', methods=['GET', 'HEAD'])
def vod(channel):
    """process request to /vod/.

    Args:
      channel: Returns: the http response

    Returns:

    """

    if CHANNEL_FILTER.match(channel):
        return process_channel(channel, request)
    else:
        abort(404)


@app.route('/vodonly/<string:channel>', methods=['GET', 'HEAD'])
def vodonly(channel):
    """process request to /vodonly/.

    Args:
      channel: Returns: the http response

    Returns:

    """
    if CHANNEL_FILTER.match(channel):
        return process_channel(channel, request)
    else:
        abort(404)


@app.route('/')
def index():
    """process request to the root."""
    return render_template('index.html')


def process_channel(channel, request):
    """process the given channel.

    Args:
      channel: the channel string given in the request
      request: the request object from flask

    Returns:
      rss_data: the fully formed rss feed

    """
    include_streaming = True if request.args.get("include_streaming", "False").lower() == "true" else False
    sort_by = request.args.get("sort_by", "published_at").lower()
    desc = True if request.args.get("desc", "False").lower() == "true" else False
    links_only = True if request.args.get("links_only", "False").lower() == "true" else False
    transcode = True if request.args.get("transcode", str(TRANSCODE)).lower() == "true" else False

    try:
        user_data = json.loads(fetch_channel(channel))['data'][0]
        channel_id = user_data['id']
        vods_data = json.loads(fetch_vods(channel_id))['data']
        streams_data = json.loads(fetch_streams(channel_id))['data']
    except KeyError as e:
        logging.error("could not fetch data for the given request")
        logging.error(e)
        abort(404)

    rss_data = construct_rss(user_data, vods_data, streams_data, include_streaming, sort_by=sort_by, desc_sort=desc, links_only=links_only, transcode = transcode, request = request)
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
    """fetches the JSON formatted list of streams for the give user

    Args:
      user_id: the unique identifier of the channel

    Returns: the JSON formatted vods list

    """
    return fetch_json(user_id, STREAMS_URL_TEMPLATE)


def get_auth_headers():
    """gets the headers for the twitch API and requests a new oauth token if needed

    Returns: a dict containing auth data

    """
    authorize()
    return {
        'Authorization': 'Bearer ' + TWITCH_OAUTH_TOKEN,
        'Client-Id': TWITCH_CLIENT_ID,
    }


@sleep_and_retry
@limits(calls=800, period=60)
def fetch_json(id, url_template):
    """fetches a JSON from the given URL template and generic id.

    Args:
      id: the unique identifier of your request
      url_template: the template for the request where id will be replaced example: 'https://api.twitch.tv/helix/videos?user_id=%s&type=all'

    Returns: the JSON response for the request

    """
    url = url_template % id
    headers = get_auth_headers()
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
        except urllib.error.HTTPError as e:
            logging.warning("Fetch exception caught: %s" % e)
            logging.warning(e.read().decode())
            retries += 1
    logging.error("max retries reached, could not get resource, id: " + id)
    abort(503)


def construct_rss(user, vods, streams, include_streams=False, sort_by="published_at", desc_sort=False, links_only=False, transcode = TRANSCODE, request=None):
    """returns the RSS for the given inputs.

    Args:
      user: the user dict
      vods: the vod dict
      streams: the streams dict
      include_streams: True if the streams should be included (Default value = False)
      sort_by: the key to sort by, the keys are the same used by the twitch API https://dev.twitch.tv/docs/api/reference#get-videos
      desc_sort: True if the sort must be done in ascending oreder
      links_only: if True the audio stream will not be fetched, makes the feed generation very fast

    Returns: fully formatted RSS string

    """

    logging.debug("processing channel")
    if links_only:
        logging.debug("links_only enabled, not fetching audio streams")
    try:
        channel_name = user['login']
        display_name = user['display_name']
        icon = user['profile_image_url']
        is_streaming = True if streams else False
    except KeyError as e:
        logging.error("error while processing user data")
        logging.error(e)
        abort(500)
    logging.debug("streaming=" + str(is_streaming))
    logging.debug("user data:")
    logging.debug(user)
    if is_streaming:
        logging.debug("streams data:")
        logging.debug(streams)

    feed = FeedGenerator()
    feed.load_extension('podcast')

    # Set the feed/channel level properties
    feed.image(url=icon)
    feed.id("https://github.com/madiele/TwitchToPodcastRSS")
    feed.title("%s's Twitch video RSS" % display_name)
    feed.link(href='https://www.twitch.tv/' + channel_name, rel='self')
    feed.author(name="Generated by TwitchToPodcastRSS version " + TTP_VERSION)
    feed.description("The RSS Feed of %s's videos on Twitch" % display_name)
    feed.podcast.itunes_author("Twitch RSS Generated")
    feed.podcast.itunes_complete(False)
    feed.podcast.itunes_explicit('no')
    feed.podcast.itunes_image(icon)
    feed.podcast.itunes_summary("The RSS Feed of %s's videos on Twitch" % display_name)
    # Create an item
    if vods:

        try:
            is_date = False
            try:
                parse_date(vods[0][sort_by])
                is_date = True
            except (ValueError, OverflowError, TypeError):
                is_date = False

            logging.debug("ordering by: " + str(sort_by) + "; desc_sort=" + str(desc_sort))
            if is_date:
                vods = sorted(vods, key=lambda kv: parse_date(kv[sort_by]), reverse=desc_sort)
            else:
                vods = sorted(vods, key=lambda kv: kv[sort_by], reverse=desc_sort)
        except KeyError:
            logging.error("can't order by " + sort_by + " resorting to ordering by id")
            sort_by = "published_at"
            try:
                vods = sorted(vods, key=lambda kv: kv['id'], reverse=False)
            except KeyError:
                logging.error("can't order by standard ordering")
        for vod in vods:
            try:

                logging.debug("processing vod:" + vod['id'])
                logging.debug(vod)
                description = ""
                if is_streaming and vod['stream_id'] == streams[0]['id']:
                    if not include_streams:
                        logging.debug("skipping incomplete vod")
                        continue
                    else:
                        description = "<p>warning: this stream is still going</p>"
                        thumb = "https://vod-secure.twitch.tv/_404/404_processing_320x180.png"
                else:
                    thumb = vod['thumbnail_url'].replace("%{width}", "512").replace("%{height}", "288")
                item = feed.add_entry()
                link = vod['url']
                item.title(vod['title'])

                description += "<a href=\"%s\"><p>%s</p><img src=\"%s\" /></a>" % (
                    link, html_escape(vod['title']), thumb)
                if vod['description']:
                    description += "<br/>" + vod['description']

                if not links_only:
                    # prevent get_audiostream_url to be run concurrenty with the same paramenter
                    # this way the next hit on get_audiostream_url will use the cache instead
                    if not transcode:
                        global streamUrl_queues
                        if link not in streamUrl_queues:
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
                            description += "<br>reason: " + str(e)
                            stream_url = None

                        q['count'] = q['count'] - 1
                        if q['count'] == 0:
                            del streamUrl_queues[link]

                        q['lock'].release()
                    else:
                        stream_url = url_for('transcode', vod_id = vod['id'], _external=True)

                    if stream_url:
                        item.enclosure(stream_url, type='audio/mpeg')

                if new_release_available():
                    description += '<br><p><a href="https://github.com/%s/releases">new version of TwitchToPodcastRSS available!</a></p>' % GITHUB_REPO

                description += '<br><br><p>Generated by TwitchToPodcastRSS ' + TTP_VERSION + '</p>'
                item.link(href=link, rel="related")
                item.description(description)
                date = datetime.datetime.strptime(vod['created_at'], '%Y-%m-%dT%H:%M:%SZ')
                item.podcast.itunes_duration(re.sub('[hm]', ':', vod['duration']).replace('s', ''))
                item.podcast.itunes_author(channel_name)
                if thumb.endswith('.jpg') or thumb.endswith('.png'):
                    item.podcast.itunes_image(thumb)

                item.pubDate(pytz.utc.localize(date))
                item.updated(pytz.utc.localize(date))
                guid = vod['id']
                # if vod["status"] == "recording":  # To show a different news item when recording is over
                # guid += "_live"
                item.guid(guid)
            except KeyError as e:
                logging.warning('Issue with json while processing vod: %s\n\nException: %s' % (vod, e))
                feed.remove_entry(item)

    logging.debug("all vods processed")
    return feed.rss_str()


# For debug
if __name__ == "__main__":
    app.run(host='127.0.0.1', port=8081, debug=True)
