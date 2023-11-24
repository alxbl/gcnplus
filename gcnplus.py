import json

from .common import InfoExtractor
from ..utils import traverse_obj

from ..networking import Request


class GcnPlusIE(InfoExtractor):
    _VALID_URL = r'https?://plus\.globalcyclingnetwork\.com/watch/(?P<id>\d+)'
    _TESTS = [
        # Tests? YOLO. It won't matter after December 19th anyway.
    ]

    # actually defined in https://netsport.eurosport.io/?variables={"databaseId":<databaseId>,"playoutType":"VDP"}&extensions={"persistedQuery":{"version":1 ..
    # but this method require to get sha256 hash
    _GEO_COUNTRIES = ['DE', 'NL', 'EU', 'IT', 'FR']  # Not complete list but it should work

    def set_info_callback(self, cb):
        self._callback = cb

    def _real_initialize(self):
        pass  # Need to use browser cookies on GCN+.

    def _real_extract(self, url):
        display_id = self._match_id(url)
        # webpage = self._download_webpage(url, display_id)

        # Get config from gcn-dl
        # HERE


        req_body = {
            "deviceInfo": {
                "adBlocker": False,
                "drmSupported": True,
                "hdrCapabilities": [
                    "SDR"
                ],
                    "hwDecodingCapabilities": [],
                    "player": {
                    "width": 1920,
                    "height": 1080
                },
                "screen": {
                    "width": 1920,
                    "height": 1080
                },
                "soundCapabilities": [
                    "STEREO"
                ]
            },
            "videoId": display_id
        }

        # Need to POST, so create an URLlib request...
        req = Request('https://disco-api-prod.globalcyclingnetwork.com/playback/v3/videoPlaybackInfo', 
                      method='POST', 
                      data=json.dumps(req_body).encode('utf8'))

        json_data = self._download_json(req, display_id) # Good?

        # Get subs/formats. This should be largely the same as Eurosport...
        formats, subtitles = [], {}
        for stream in json_data["data"]['attributes']['streaming']:
            stream_type = stream["type"]
            if stream_type == 'hls':
                fmts, subs = self._extract_m3u8_formats_and_subtitles(stream["url"], display_id, ext='mp4')
            elif stream_type == 'dash':
                fmts, subs = self._extract_mpd_formats_and_subtitles(stream["url"], display_id)
            elif stream_type == 'mss':
                fmts, subs = self._extract_ism_formats_and_subtitles(stream["url"], display_id)

            formats.extend(fmts)
            self._merge_subtitles(subs, target=subtitles)

        # TODO: Fill this from metadata scraped by gcn-dl
        info = self._callback(display_id)
        return {
            'id': json_data['data']['id'],
            'title': info["title"],
            'display_id': display_id,
            'formats': formats,
            'subtitles': subtitles,
            'thumbnails': [],  # Can it download data from disk? doubtful.
            'description': info["details"],
            'duration': info["duration"] / 1000, # GCN+ uses milliseconds
        }
