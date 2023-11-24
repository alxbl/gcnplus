import json
from os import path
import requests

import yt_dlp

DST='data'  # Folder to write the video data to
USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0'
# Some helpful constants.
GCN_TOKEN    = 'replace'  # Put your JWT here.
GCN_ENDPOINT = 'https://disco-api-prod.globalcyclingnetwork.com/'

GCN_RENEW_TOKEN_URL='token?realm=gcn'  # .included[type==image:first].src
GCN_LIST_COLLECTIONS_URL='cms/routes/mobile-landing-page?include=default&page[items.size]={}&page[items.number]={}'
GCN_LIST_VIDEOS_URL='cms/collections/{}?include=default&page[items.size]={}&page[items.number]={}'
GCN_THUMBNAIL_URL='content/videos/{}?include=images'
GCN_VIDEO_INFO_URL='playback/v3/videoPlaybackInfo'

# The number of collection pages which have interesting results. This seems to be 2 currently.
GCN_NUM_COLLECTION_PAGES = 2

# mobile-landing-page gives the collections including a .meta section which reports how many pages there are:
#  {"id":"120311406408740576566218416803134666459","meta":{
#   "itemsCurrentPage" : 1,
#   "itemsPageSize" : 10,
#   "itemsTotalPages" : 1}


S = requests.Session()
S.cookies.set("st", GCN_TOKEN)
S.headers["User-Agent"] = USER_AGENT

def wget_if_not_present(url, dst):
    if path.exists(dst):
        return

    print(f'[*] Downloading {url}')
    rsp = S.get(url)

    if not rsp.ok:
        raise Exception('wget failed')

    with open(dst, 'wb') as o:
        o.write(rsp.content)

def request_or_read_from_file(req_func, file):
    if path.exists(file):
        with open(file, 'r') as f:
            # print(f'[*]   Using cached result from {file}')
            return json.load(f)
    else:
        rsp = req_func()
        if rsp.ok:
            with open(file, 'w') as f:
                f.write(rsp.text)
        else:
            print('ERROR!\n' + rsp.text)

            raise Exception('Request failed!')
        return json.loads(rsp.text)



# Dump collections
collections = {}
page = 1
for p in range(GCN_NUM_COLLECTION_PAGES):
    print(f"[*] Listing collections page {p}...")
    file = path.join(DST, 'requests', f'collections-{p+1}.json')
    rsp = request_or_read_from_file(lambda : S.get(GCN_ENDPOINT + GCN_LIST_COLLECTIONS_URL.format(10, p+1)), file)

    for item in rsp["included"]:
        if item["type"] == "collection":
            c = item["attributes"]["alias"]
            if c not in collections:
                collections[c] = item

print(f'[+] Discovered {len(collections)} collections...')

# Get all videos
videos = {}
for alias, collection in collections.items():
    print(f'[*] Scraping videos that are part of `{alias}` collection...')

    try:
        if collection["attributes"]["kind"] == "manual":
            print(f'[!] Skipping {alias} because it is a manual collection.')
            continue

        num_pages = collection["meta"]["itemsTotalPages"]
        per_page  = collection["meta"]["itemsPageSize"]
        id        = collection["id"]

        for p in range(num_pages):
            file = path.join(DST, 'requests', f'{alias}-{p+1}.json')
            rsp = request_or_read_from_file(lambda: S.get(GCN_ENDPOINT + GCN_LIST_VIDEOS_URL.format(id, per_page, p+1)), file)

            count = 0
            for video in rsp["included"]:
                if video["type"] != "video":
                    continue

                vid = video["id"]
                if vid not in videos:
                    count += 1
                    videos[vid] = video
            if count > 0:
                print(f'[+]   Found {count} new video(s)')

    except Exception as e:
        print('ERROR: ' + str(e))
        exit(1)

print(f'[+] Found {len(videos)} videos available')

# Little hook function that YT-DLP will invoke to get the metadata of a video...
# OOPS: Can't pass a function as arg...
def get_metadata(id):
    global videos

    video = videos[id]

    return {
        "duration": video["attributes"]["videoDuration"],
        "title": video["attributes"]["name"],
        "summary": video["attributes"]["description"],
        "details": video["attributes"]["longDescription"]
    }

# TODO: Set output path.
ydl = yt_dlp.YoutubeDL(params={
    "cookiesfrombrowser": ("firefox",),


})

gcnplus = ydl.get_info_extractor('GcnPlus')
gcnplus.set_info_callback(get_metadata)

urls = []
# DOWNLOAD EVERYTHING
for id, video in videos.items():
    drm = video["attributes"]["drmEnabled"]

    if drm:
        print(f'[!]   DRM is enabled for this video! Download might fail.')

    file = path.join(DST, 'requests', f'{id}.json')

    # Get thumbnails
    rsp = request_or_read_from_file(lambda: S.get(GCN_ENDPOINT + GCN_THUMBNAIL_URL.format(id)), file)
    for item in rsp["included"]:
        if item["type"] != "image":
            continue

        w = item["attributes"]["width"]
        h = item["attributes"]["height"]
        url = item["attributes"]["src"]

        file = path.join(DST, 'thumbnails', f'{id}_{w}_{h}.jpg')
        wget_if_not_present(url, file)

    # Download the video if not already present.
    #  export PYTHONPATH=~/Code/github.com/yt-dlp/yt-dlp

    outname = f'{video["attributes"]["name"]} [{id}].mp4'.replace(':', '：')
    on_disk = path.join('/mnt/Video/GCN+', outname)
    print(f'Check {on_disk}...')

    if path.exists(on_disk) or path.exists(outname):
        print(f'  Already downloaded')
        continue
    urls.append(f'https://plus.globalcyclingnetwork.com/watch/{id}')

ydl.download(urls)



