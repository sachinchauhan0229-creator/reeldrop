"""Stream a public Instagram video as an attachment from ReelDrop itself."""
import json
import time
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, urlopen, HTTPRedirectHandler, build_opener

from api.direct import extract, normalize, media_url, _slots, _lock, _requests


class CDNRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not media_url(newurl):
            raise ValueError('Unexpected media destination')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


class handler(BaseHTTPRequestHandler):
    def error_json(self, status, message):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(json.dumps({'error': message}).encode())

    def do_GET(self):
        args = parse_qs(urlsplit(self.path).query)
        url = normalize(args.get('url', [''])[0])
        try:
            index = int(args.get('index', ['0'])[0])
        except ValueError:
            return self.error_json(400, 'Invalid video selection.')
        if not url or index < 0 or index > 19:
            return self.error_json(400, 'Use a public Instagram video link.')
        if self.headers.get('Sec-Fetch-Site') == 'cross-site':
            return self.error_json(403, 'Start the download from ReelDrop.')
        ip = self.headers.get('x-forwarded-for', 'unknown').split(',')[0]
        now = time.monotonic()
        with _lock:
            for key in list(_requests):
                if _requests[key][1] < now:
                    del _requests[key]
            used, reset = _requests.get(ip, (0, now + 60))
            if used >= 6 or len(_requests) > 5000:
                return self.error_json(429, 'Please wait a minute before downloading more videos.')
            _requests[ip] = (used + 1, reset)
        if not _slots.acquire(blocking=False):
            return self.error_json(429, 'The downloader is busy. Please try again shortly.')
        started = False
        try:
            media = extract(url)
            if index >= len(media):
                return self.error_json(404, 'This video is no longer available.')
            target = media_url(media[index].get('url'))
            if not target:
                return self.error_json(502, 'No downloadable video was found.')
            request = Request(target, headers={'User-Agent': 'Mozilla/5.0', 'Referer': 'https://www.instagram.com/'})
            with build_opener(CDNRedirects()).open(request, timeout=15) as upstream:
                if not upstream.headers.get('Content-Type', '').lower().startswith('video/'):
                    return self.error_json(502, 'Instagram did not return a video. Please retry.')
                filename = f'ReelDrop-{url.rstrip("/").split("/")[-1]}-{index + 1}.mp4'
                # Leave out Content-Length so Vercel streams the body instead of buffering it.
                self.send_response(200)
                self.send_header('Content-Type', 'video/mp4')
                self.send_header('Content-Disposition', f'attachment; filename="{filename}"')
                self.send_header('Cache-Control', 'no-store')
                self.send_header('X-Content-Type-Options', 'nosniff')
                if upstream.headers.get('Content-Length', '').isdigit():
                    self.send_header('X-Media-Size', upstream.headers['Content-Length'])
                self.end_headers()
                started = True
                while chunk := upstream.read(65536):
                    self.wfile.write(chunk)
                    self.wfile.flush()
        except Exception:
            if not started:
                self.error_json(502, 'Instagram could not deliver this video. Please try again.')
            else:
                self.close_connection = True
        finally:
            _slots.release()

