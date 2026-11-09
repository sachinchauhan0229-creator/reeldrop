"""Run the private YouTube worker behind an HTTPS reverse proxy or tunnel."""

import hmac
import os
import re
import sys
from http.server import ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from api.youtube import handler


TOKEN = os.environ.get('REELDROP_YOUTUBE_WORKER_TOKEN', '')


class Worker(handler):
    def do_POST(self):
        provided = self.headers.get('Authorization', '').encode('utf-8')
        if self.path != '/api/youtube' or not hmac.compare_digest(provided, ('Bearer ' + TOKEN).encode()):
            return self.youtube_json(403, {'error': 'Forbidden'})
        client = self.headers.get('X-ReelDrop-Client', '')
        if not re.fullmatch(r'[0-9a-f]{64}', client):
            return self.youtube_json(400, {'error': 'Invalid request'})
        if 'x-forwarded-for' in self.headers:
            del self.headers['x-forwarded-for']
        self.headers['x-forwarded-for'] = client
        return self.handle_youtube(use_worker=False)

    def log_message(self, *_args):
        pass


if __name__ == '__main__':
    if len(TOKEN) < 32:
        raise SystemExit('Set REELDROP_YOUTUBE_WORKER_TOKEN to a random secret of at least 32 characters.')
    port = int(os.environ.get('REELDROP_YOUTUBE_WORKER_PORT', '3044'))
    print(f'ReelDrop YouTube worker listening on 127.0.0.1:{port}', flush=True)
    ThreadingHTTPServer(('127.0.0.1', port), Worker).serve_forever()
