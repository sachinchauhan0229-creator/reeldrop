"""Experimental public Instagram extraction, without a paid media API."""
import json
import re
import threading
import time
from http.server import BaseHTTPRequestHandler
from urllib.parse import urlsplit

import yt_dlp

_lock = threading.Lock()
_requests = {}
_slots = threading.BoundedSemaphore(2)


def normalize(value):
    if not isinstance(value, str) or len(value) > 2048:
        return None
    try:
        url = urlsplit(value.strip())
        match = re.fullmatch(r'/(p|reel|reels|tv)/([A-Za-z0-9_-]{5,64})/?', url.path)
        if (url.scheme != 'https' or url.hostname not in ('instagram.com', 'www.instagram.com', 'm.instagram.com')
                or url.username or url.password or url.port or not match):
            return None
        kind = 'reel' if match[1] == 'reels' else match[1]
        return f'https://www.instagram.com/{kind}/{match[2]}/'
    except ValueError:
        return None


def media_url(value):
    if not isinstance(value, str):
        return None
    try:
        url = urlsplit(value)
        if url.scheme != 'https' or url.username or url.password or url.port:
            return None
        if any(url.hostname == domain or url.hostname.endswith('.' + domain)
               for domain in ('cdninstagram.com', 'fbcdn.net')):
            return value
    except (ValueError, AttributeError):
        pass
    return None


class QuietLogger:
    def debug(self, _message): pass
    def info(self, _message): pass
    def warning(self, _message): pass
    def error(self, _message): pass


def extract(url):
    options = {'quiet': True, 'no_warnings': True, 'logger': QuietLogger(), 'skip_download': True,
               'cachedir': False, 'socket_timeout': 8, 'retries': 0, 'extractor_retries': 0,
               'playlistend': 20, 'noplaylist': False, 'format': 'best[ext=mp4]/best'}
    with yt_dlp.YoutubeDL(options) as downloader:
        info = downloader.extract_info(url, download=False)
    items = info.get('entries') or [info]
    result, seen = [], set()
    for index, item in enumerate(items):
        if index >= 20:
            break
        if not item:
            continue
        link = media_url(item.get('url'))
        if not link:
            for fmt in reversed(item.get('formats') or []):
                if fmt.get('vcodec') != 'none' and fmt.get('acodec') != 'none':
                    link = media_url(fmt.get('url'))
                    if link:
                        break
        if link and link not in seen:
            seen.add(link)
            result.append({'url': link, 'type': 'video'})
    return result


class handler(BaseHTTPRequestHandler):
    def send_json(self, status, data):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

    def do_GET(self):
        self.send_json(405, {'error': 'Use POST.'})

    def do_POST(self):
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if length < 1 or length > 8192:
                return self.send_json(400, {'error': 'Invalid request size.'})
            url = normalize(json.loads(self.rfile.read(length)).get('url'))
        except (ValueError, AttributeError):
            return self.send_json(400, {'error': 'Invalid request.'})
        if not url:
            return self.send_json(400, {'error': 'Use a public Instagram post or Reel link.'})
        ip = self.headers.get('x-forwarded-for', 'unknown').split(',')[0]
        now = time.monotonic()
        with _lock:
            for key in list(_requests):
                if _requests[key][1] < now:
                    del _requests[key]
            used, reset = _requests.get(ip, (0, now + 60))
            if used >= 3 or len(_requests) > 5000:
                return self.send_json(429, {'error': 'Please wait a minute and try again.'})
            _requests[ip] = (used + 1, reset)
        if not _slots.acquire(blocking=False):
            return self.send_json(429, {'error': 'The service is busy. Please try again shortly.'})
        try:
            media = extract(url)
            if not media:
                return self.send_json(404, {'error': 'No public video could be retrieved.'})
            return self.send_json(200, {'media': media})
        except yt_dlp.utils.DownloadError:
            return self.send_json(502, {'error': 'Instagram did not allow this download. Try another public video later.'})
        except Exception:
            return self.send_json(502, {'error': 'Video extraction is temporarily unavailable.'})
        finally:
            _slots.release()
