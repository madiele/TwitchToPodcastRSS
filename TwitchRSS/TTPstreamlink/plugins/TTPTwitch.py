from streamlink.plugins.twitch import Twitch, TwitchAPI
from os import environ


class TTPTwitchAPI(TwitchAPI):
    TWITCH_CLIENT_ID = environ.get("TWITCH_CLIENT_ID")


class TTPTwitch(Twitch):
    def __init__(self, url):
        super().__init__(url)
        self.api = TTPTwitchAPI(session=self.session)

__plugin__ = TTPTwitch
