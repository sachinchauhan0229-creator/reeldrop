"""Public media REST endpoint. No paid API or Instagram account credentials."""
import json
import sys
from pathlib import Path
from http.server import BaseHTTPRequestHandler
if __package__ in (None, ''):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from reeldrop_media import extract_payload, normalize, media_url, MediaError, throttle, _slots, _requests, _lock

def extract(url, mode='all'):
    return extract_payload(url, mode)['media']

class handler(BaseHTTPRequestHandler):
    def send_json(self, status, data):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Cache-Control', 'no-store')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())
    def do_GET(self):
        self.send_json(405, {'error':'Use POST.', 'code':'METHOD_NOT_ALLOWED', 'documentation':'/api.html'})
    def do_POST(self):
        acquired=False
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0 < length <= 8192:
                raise MediaError('Invalid request size.', 'INVALID_REQUEST', 400)
            data=json.loads(self.rfile.read(length))
            if not isinstance(data,dict):
                raise MediaError('Send a JSON object.', 'INVALID_REQUEST', 400)
            url=normalize(data.get('url'),data.get('mode','all'))
            if not url:
                raise MediaError('Paste a public Instagram link or use a username in Viewer mode.', 'INVALID_URL', 400)
            throttle(self.headers.get('x-forwarded-for','unknown').split(',')[0])
            acquired=_slots.acquire(blocking=False)
            if not acquired:
                raise MediaError('The service is busy. Please try again shortly.', 'BUSY', 429)
            return self.send_json(200, extract_payload(url,data.get('mode','all')))
        except MediaError as error:
            return self.send_json(error.status, {'error':str(error), 'code':error.code})
        except (ValueError,TypeError,AttributeError):
            return self.send_json(400, {'error':'Invalid request.', 'code':'INVALID_REQUEST'})
        except Exception:
            return self.send_json(502, {'error':'Instagram is temporarily unavailable. Please try later.', 'code':'INSTAGRAM_UNAVAILABLE'})
        finally:
            if acquired:_slots.release()

if __name__=='__main__':
    try:
        print(json.dumps(extract_payload(sys.argv[1] if len(sys.argv)>1 else '', sys.argv[2] if len(sys.argv)>2 else 'all')))
    except MediaError as error:
        print(json.dumps({'error':str(error),'code':error.code,'status':error.status}))
    except Exception:
        print(json.dumps({'error':'Instagram is temporarily unavailable.','code':'INSTAGRAM_UNAVAILABLE','status':502}))
