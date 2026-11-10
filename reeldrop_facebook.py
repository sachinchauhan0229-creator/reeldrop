"""Look up progressive MP4 sources for public Facebook videos."""
import re
from urllib.parse import parse_qs, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

import yt_dlp
from yt_dlp.extractor.facebook import FacebookIE

from reeldrop_media import MediaError, QuietLogger, media_url, variants


FACEBOOK_HOSTS = ('facebook.com', 'www.facebook.com', 'm.facebook.com')
VIDEO_ID = r'[0-9]{5,30}'
SHARE_PATH = r'/share/[rv]/[A-Za-z0-9_-]{4,100}'


def facebook_url(value):
    if not isinstance(value, str) or len(value) > 4096:
        return None
    value = value.strip()
    if value.startswith(tuple(host + '/' for host in (*FACEBOOK_HOSTS, 'fb.watch'))):
        value = 'https://' + value
    try:
        url = urlsplit(value)
        if url.scheme != 'https' or url.username or url.password or url.port:
            return None
    except ValueError:
        return None
    path = url.path.rstrip('/')
    if url.hostname == 'fb.watch' and re.fullmatch(r'/[A-Za-z0-9_-]{4,100}', path):
        return 'https://fb.watch' + path + '/'
    if url.hostname not in FACEBOOK_HOSTS:
        return None
    if re.fullmatch(SHARE_PATH, path):
        return 'https://www.facebook.com' + path + '/'
    reel = re.fullmatch(r'/reel/(' + VIDEO_ID + ')', path)
    if reel:
        return 'https://m.facebook.com/watch/?v=' + reel[1] + '&_rdr'
    video = re.fullmatch(r'/(?:[A-Za-z0-9._-]+/)?videos/(' + VIDEO_ID + ')', path)
    ids = parse_qs(url.query).get('v', [])
    if video:
        return 'https://www.facebook.com/watch/?v=' + video[1]
    if path in ('/watch', '/video.php', '/video/video.php') and len(ids) == 1 and re.fullmatch(VIDEO_ID, ids[0]):
        return f'https://{url.hostname}/watch/?v={ids[0]}'
    return None


def is_share(url):
    return urlsplit(url).hostname == 'fb.watch' or urlsplit(url).path.startswith('/share/')


class ShareRedirects(HTTPRedirectHandler):
    def http_error_302(self, req, fp, code, msg, headers):
        return fp

    http_error_301 = http_error_303 = http_error_307 = http_error_308 = http_error_302


def resolve_share(url):
    opener = build_opener(ShareRedirects())
    for _ in range(4):
        request = Request(url, headers={'User-Agent': 'Mozilla/5.0'})
        with opener.open(request, timeout=6) as response:
            location = response.headers.get('Location')
        url = facebook_url(urljoin(url, location)) if location else None
        if not url:
            break
        if not is_share(url):
            return url
    raise ValueError('Facebook share link did not resolve to a video')


def facebook_cdn(value):
    if media_url(value):
        host = urlsplit(value).hostname
        if host == 'fbcdn.net' or host.endswith('.fbcdn.net'):
            return value
    return None


def extract_facebook(url):
    options = {'quiet': True, 'logger': QuietLogger(), 'cachedir': False,
               'socket_timeout': 8, 'retries': 0, 'extractor_retries': 0}
    try:
        if is_share(url):
            url = resolve_share(url)
        with yt_dlp.YoutubeDL(options) as downloader:
            info = FacebookIE(downloader).extract(url)
    except Exception as error:
        raise MediaError('Facebook did not make this video available. Check that it is public and try its direct video or Reel link.',
                         'FACEBOOK_UNAVAILABLE', 422) from error

    labels = {'hd': 'HD', 'sd': 'SD'}
    candidates = [
        item for item in info.get('formats', [])
        if item.get('vcodec') != 'none' and item.get('acodec') != 'none'
        and (item.get('ext') == 'mp4' or item.get('format_id') in labels)
        and item.get('protocol', 'https') in ('https', 'http')
        and facebook_cdn(item.get('url'))
    ]
    candidates.sort(key=lambda item: item.get('format_id') == 'hd', reverse=True)
    choices = variants(candidates, 'video')
    if not choices:
        raise MediaError('No downloadable Facebook MP4 was found for this link.', 'FACEBOOK_NO_FORMAT', 422)
    label_by_url = {item['url']: labels.get(item.get('format_id')) for item in candidates}
    for choice in choices:
        if not (choice['width'] and choice['height']) and label_by_url[choice['url']]:
            choice['label'] = label_by_url[choice['url']]
    video = {'id': str(info.get('id') or 'facebook-video'), 'type': 'video', 'index': 0,
             'url': choices[0]['url'], 'thumbnail': facebook_cdn(info.get('thumbnail')),
             'variants': choices, 'width': choices[0]['width'], 'height': choices[0]['height']}
    return {'sourceUrl': url, 'kind': 'video', 'media': [video], 'warnings': [],
            'post': {'caption': str(info.get('title') or 'Facebook video')[:5000]}}
