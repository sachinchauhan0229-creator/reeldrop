"""Public Instagram metadata shared by the web app, REST API and MCP endpoint."""
import copy
import hashlib
import re
import threading
import time
from itertools import islice
from urllib.parse import urlsplit, urlencode

import yt_dlp
from yt_dlp.extractor.instagram import InstagramIE, InstagramStoryIE

MAX_ITEMS = 20
_cache = {}
_cache_lock = threading.Lock()
_slots = threading.BoundedSemaphore(2)
_requests = {}
_lock = threading.Lock()
MODES = {'all', 'video', 'photo', 'reels', 'story', 'igtv', 'carousel', 'viewer'}


class MediaError(Exception):
    def __init__(self, message, code='UNAVAILABLE', status=502):
        super().__init__(message)
        self.code, self.status = code, status


def normalize(value, mode='all'):
    if not isinstance(value, str) or len(value) > 4096:
        return None
    value = value.strip()
    if mode in ('viewer', 'story') and re.fullmatch(r'@?[A-Za-z0-9_.]{1,30}', value):
        value = 'https://www.instagram.com/' + value.lstrip('@') + '/'
    if value.startswith(('instagram.com/', 'www.instagram.com/', 'm.instagram.com/')):
        value = 'https://' + value
    try:
        url = urlsplit(value)
        if url.scheme != 'https' or url.hostname not in ('instagram.com', 'www.instagram.com', 'm.instagram.com') or url.username or url.password or url.port:
            return None
        match = re.fullmatch(r'/(p|reel|reels|tv)/([A-Za-z0-9_-]{5,64})/?', url.path)
        if match:
            return f'https://www.instagram.com/{"reel" if match[1] == "reels" else match[1]}/{match[2]}/'
        story = re.fullmatch(r'/stories/([A-Za-z0-9_.]{1,30})/(\d{5,30})/?', url.path)
        if story:
            return f'https://www.instagram.com/stories/{story[1]}/{story[2]}/'
        profile = re.fullmatch(r'/([A-Za-z0-9_.]{1,30})/?', url.path)
        if profile and mode in ('viewer', 'story') and profile[1] not in ('accounts', 'explore', 'direct', 'stories', 'reels', 'about', 'api'):
            return f'https://www.instagram.com/{profile[1]}/'
    except ValueError:
        pass
    return None


def media_url(value):
    if not isinstance(value, str) or len(value) > 12000:
        return None
    try:
        url = urlsplit(value)
        if url.scheme == 'https' and not (url.username or url.password or url.port) and any(url.hostname == d or url.hostname.endswith('.' + d) for d in ('cdninstagram.com', 'fbcdn.net')):
            return value
    except (ValueError, AttributeError):
        pass
    return None


def throttle(ip, limit=8):
    now = time.monotonic()
    with _lock:
        for key in list(_requests):
            if _requests[key][1] < now:
                del _requests[key]
        used, reset = _requests.get(ip, (0, now + 60))
        if used >= limit or len(_requests) >= 5000:
            raise MediaError('Please wait a minute before trying again.', 'RATE_LIMIT', 429)
        _requests[ip] = (used + 1, reset)


class QuietLogger:
    def debug(self, _message): pass
    def info(self, _message): pass
    def warning(self, _message): pass
    def error(self, _message): pass


class CapturePostIE(InstagramIE):
    def _extract_product(self, product_info, *args, **kwargs):
        self.products.append(product_info[0] if isinstance(product_info, list) else product_info)
        return super()._extract_product(product_info, *args, **kwargs)


class CaptureStoryIE(InstagramStoryIE):
    def _extract_product(self, product_info, *args, **kwargs):
        self.products.append(product_info[0] if isinstance(product_info, list) else product_info)
        return super()._extract_product(product_info, *args, **kwargs)


def _integer(value):
    try:
        return max(0, int(value or 0))
    except (ValueError, TypeError):
        return 0


def variants(candidates, kind):
    safe = []
    for item in candidates or []:
        if not isinstance(item, dict):
            continue
        url = media_url(item.get('url'))
        if url:
            width, height = _integer(item.get('width')), _integer(item.get('height'))
            safe.append({'url': url, 'width': width, 'height': height, 'label': f'{width} × {height}' if width and height else 'Original', 'type': kind})
    safe.sort(key=lambda v: v['width'] * v['height'], reverse=True)
    result, seen = [], set()
    for item in safe:
        key = (item['width'], item['height']) if item['width'] and item['height'] else item['url']
        if key not in seen:
            seen.add(key)
            item['id'] = str(len(result))
            result.append(item)
    return result[:10]


def product_media(product):
    """Preserve the original order of photo/video carousel children."""
    result = []
    for node in (product.get('carousel_media') or [product])[:MAX_ITEMS]:
        if not isinstance(node, dict):
            continue
        video = variants(node.get('video_versions'), 'video')
        images = variants((node.get('image_versions2') or {}).get('candidates'), 'image')
        is_video = node.get('media_type') == 2 or bool(node.get('video_versions')) or bool(node.get('video_duration'))
        kind, choices = ('video', video) if is_video else ('image', images)
        if not choices:
            continue
        result.append({'id': str(node.get('pk') or node.get('id') or len(result)), 'type': kind,
                       'url': choices[0]['url'], 'width': choices[0]['width'], 'height': choices[0]['height'],
                       'thumbnail': images[0]['url'] if images else None, 'variants': choices,
                       'duration': node.get('video_duration') if kind == 'video' else None})
    return result


def _fallback_info(info):
    result = []
    for item in list(info.get('entries') or [info])[:MAX_ITEMS]:
        if not item:
            continue
        candidates = [f for f in item.get('formats', []) if f.get('vcodec') != 'none' and f.get('acodec') != 'none' and f.get('protocol', 'https') in ('https', 'http')]
        if media_url(item.get('url')):
            candidates.append({'url': item['url'], 'width': item.get('width'), 'height': item.get('height')})
        choices = variants(candidates, 'video')
        if choices:
            result.append({'id': str(item.get('id') or len(result)), 'type': 'video', 'url': choices[0]['url'],
                           'thumbnail': media_url(item.get('thumbnail')), 'variants': choices,
                           'width': choices[0]['width'], 'height': choices[0]['height'], 'duration': item.get('duration')})
    return result


def _profile(url):
    from curl_cffi import requests
    username = urlsplit(url).path.strip('/')
    response = requests.get('https://www.instagram.com/api/v1/users/web_profile_info/?' + urlencode({'username': username}),
                            headers={'X-IG-App-ID': '936619743392459', 'Referer': url}, impersonate='chrome', timeout=12, allow_redirects=False)
    if response.status_code != 200:
        raise MediaError('Instagram is not allowing public profile access right now. Try a direct post link.', 'PROFILE_UNAVAILABLE', 422)
    try:
        user = response.json()['data']['user']
    except (ValueError, KeyError, TypeError):
        raise MediaError('This public profile could not be retrieved. Try a direct post link.', 'PROFILE_UNAVAILABLE', 422)
    if user.get('is_private'):
        raise MediaError('Private accounts are not supported.', 'PRIVATE_ACCOUNT', 422)
    return {'sourceUrl': url, 'kind': 'profile', 'profile': {'username': user.get('username', username),
            'fullName': user.get('full_name', ''), 'biography': user.get('biography', ''),
            'avatar': media_url(user.get('profile_pic_url_hd') or user.get('profile_pic_url')),
            'followers': _integer((user.get('edge_followed_by') or {}).get('count')),
            'following': _integer((user.get('edge_follow') or {}).get('count')),
            'posts': _integer((user.get('edge_owner_to_timeline_media') or {}).get('count'))}, 'media': [],
            'warnings': ['Public profile access depends on Instagram. For a specific download, paste its post or Story URL.']}


def extract_payload(value, mode='all'):
    if mode not in MODES:
        raise MediaError('Choose a supported tool.', 'INVALID_MODE', 400)
    url = normalize(value, mode)
    if not url:
        raise MediaError('Paste a public Instagram post, Reel or Story link. Use a username in Viewer mode.', 'INVALID_URL', 400)
    key = hashlib.sha256((url + ':' + mode).encode()).hexdigest()
    now = time.monotonic()
    with _cache_lock:
        for old in list(_cache):
            if _cache[old][0] < now:
                del _cache[old]
        if key in _cache:
            return copy.deepcopy(_cache[key][1])
    is_profile = len(urlsplit(url).path.strip('/').split('/')) == 1
    is_story = '/stories/' in url or (is_profile and mode == 'story')
    if is_profile and not is_story:
        payload = _profile(url)
    else:
        if is_profile:
            url = 'https://www.instagram.com/stories/' + urlsplit(url).path.strip('/') + '/'
        options = {'quiet': True, 'no_warnings': True, 'logger': QuietLogger(), 'skip_download': True,
                   'cachedir': False, 'socket_timeout': 10, 'retries': 0, 'extractor_retries': 0,
                   'ignore_no_formats_error': True, 'playlistend': MAX_ITEMS, 'noplaylist': False}
        with yt_dlp.YoutubeDL(options) as downloader:
            extractor = (CaptureStoryIE if is_story else CapturePostIE)(downloader)
            extractor.products = []
            try:
                info = extractor.extract(url)
                if info and info.get('entries') is not None:
                    info['entries'] = list(islice(info['entries'], MAX_ITEMS))
            except Exception:
                if not extractor.products:
                    raise MediaError('Instagram requires login or is restricting this Story. No passwords or private-account access are supported.' if is_story else 'Instagram did not allow access to this post. Check that it is public and try again later.',
                                     'STORY_ACCESS_RESTRICTED' if is_story else 'INSTAGRAM_UNAVAILABLE', 422)
                info = {}
            products = extractor.products
        media = [item for product in products for item in product_media(product)][:MAX_ITEMS]
        if not media and info:
            media = _fallback_info(info)
        if not media:
            raise MediaError('No accessible photos or videos were found.', 'NO_MEDIA', 404)
        # Filter without changing indices used by downloads: each card retains its source index.
        for index, item in enumerate(media):
            item['index'] = index
        product = products[0] if products else {}
        user = product.get('user') or {}
        payload = {'sourceUrl': normalize(value, mode), 'kind': 'story' if is_story else 'carousel' if len(media) > 1 else media[0]['type'],
                   'post': {'caption': (product.get('caption') or {}).get('text', '')[:5000],
                            'author': user.get('username', ''), 'authorName': user.get('full_name', '')},
                   'media': media, 'warnings': []}
    with _cache_lock:
        if len(_cache) >= 32:
            _cache.pop(next(iter(_cache)))
        _cache[key] = (time.monotonic() + 90, copy.deepcopy(payload))
    return payload
