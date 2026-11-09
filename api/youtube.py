"""Inspect public YouTube videos and stream an MP4 at the selected resolution."""
import json
import re
import tempfile
import threading
import time
from http.server import BaseHTTPRequestHandler
from pathlib import Path

from reeldrop_media import MediaError, throttle
from reeldrop_youtube import lookup, make_mp4, youtube_url
from reeldrop_youtube_alerts import notify_youtube_signin_required
from reeldrop_youtube_session import read_youtube_session
from reeldrop_youtube_worker import worker_media_size, worker_request

slots = threading.BoundedSemaphore(1)


class handler(BaseHTTPRequestHandler):
    def youtube_json(self, status, payload):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())

    def do_POST(self):
        return self.handle_youtube(use_worker=True)

    def handle_youtube(self, use_worker):
        acquired = started = False
        try:
            if self.headers.get('Sec-Fetch-Site') == 'cross-site':
                raise MediaError('Start the download from ReelDrop.', 'ORIGIN_DENIED', 403)
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= 8192:
                raise ValueError('Invalid request size')
            data = json.loads(self.rfile.read(length))
            if not isinstance(data, dict):
                raise ValueError('Invalid request')
            url = youtube_url(data.get('url'))
            if not url:
                raise MediaError('Paste a YouTube video or Shorts link.', 'YOUTUBE_INVALID_URL', 400)
            quality = data.get('quality')
            if quality is not None and (type(quality) is not int or not 1 <= quality <= 1080):
                raise ValueError('Invalid resolution')
            client = self.headers.get('x-forwarded-for', 'unknown').split(',')[0]
            throttle(client + ':youtube', 8)
            video_id = url[-11:]
            upstream = worker_request(url, quality, client) if use_worker else None
            if upstream is not None:
                with upstream:
                    if quality is None:
                        if upstream.headers.get_content_type() != 'application/json':
                            raise MediaError('The shared downloader returned an invalid result.', 'WORKER_INVALID_RESULT', 502)
                        return self.youtube_json(200, json.loads(upstream.read(32768)))
                    remaining = worker_media_size(upstream)
                    self.youtube_video_headers(video_id, quality, remaining)
                    started = True
                    while remaining:
                        chunk = upstream.read(min(65536, remaining))
                        if not chunk:
                            break
                        self.wfile.write(chunk)
                        self.wfile.flush()
                        remaining -= len(chunk)
                return
            acquired = slots.acquire(blocking=False)
            if not acquired:
                raise MediaError('YouTube downloads are busy. Try again shortly.', 'BUSY', 429)
            deadline = time.monotonic() + 48
            try:
                session = read_youtube_session() if use_worker else None
            except ValueError as error:
                raise MediaError('The server needs a fresh YouTube session.',
                                 'YOUTUBE_SIGNIN_REQUIRED', 422) from error
            except RuntimeError as error:
                raise MediaError('The server could not load its YouTube session. Try again later.',
                                 'YOUTUBE_SESSION_UNAVAILABLE', 503) from error
            info, formats = lookup(url, session=session)
            title = str(info.get('title') or 'YouTube video')[:200]
            if quality is None:
                choices = [{'height': height, 'label': f'{height}p' + (' Full HD' if height == 1080 else '')}
                           for height in formats]
                item = {'id': video_id, 'type': 'video', 'youtubeUrl': url, 'variants': choices}
                return self.youtube_json(200, {'media': [item], 'post': {'caption': title}})
            if quality not in formats:
                raise MediaError('This resolution is no longer available. Find the video again.', 'YOUTUBE_NO_FORMAT', 422)
            with tempfile.TemporaryDirectory(prefix='reeldrop-yt-') as tmp:
                target = make_mp4(formats[quality], Path(tmp), deadline)
                self.youtube_video_headers(video_id, quality, target.stat().st_size)
                started = True
                with target.open('rb') as source:
                    while chunk := source.read(65536):
                        self.wfile.write(chunk)
                        self.wfile.flush()
        except MediaError as error:
            if not started:
                if use_worker and error.code == 'YOUTUBE_SIGNIN_REQUIRED':
                    notify_youtube_signin_required()
                self.youtube_json(error.status, {'error': str(error), 'code': error.code})
        except (ValueError, UnicodeError):
            if not started:
                self.youtube_json(400, {'error': 'Invalid YouTube request.', 'code': 'INVALID_REQUEST'})
        except Exception:
            if not started:
                self.youtube_json(502, {'error': 'YouTube could not deliver this MP4. Try again or choose a smaller resolution.',
                                        'code': 'YOUTUBE_TRANSFER_FAILED'})
            else:
                self.close_connection = True
        finally:
            if acquired:
                slots.release()

    def youtube_video_headers(self, video_id, quality, size):
        filename = re.sub(r'[^A-Za-z0-9_-]', '', video_id)
        self.send_response(200)
        self.send_header('Content-Type', 'video/mp4')
        self.send_header('Content-Disposition', f'attachment; filename="ReelDrop-{filename}-{quality}p.mp4"')
        self.send_header('X-Media-Size', str(size))
        self.send_header('Cache-Control', 'no-store')
        self.send_header('X-Content-Type-Options', 'nosniff')
        self.end_headers()
