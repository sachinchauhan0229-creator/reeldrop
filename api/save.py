"""Stream validated Instagram photos/videos from the same site; never an arbitrary proxy."""
import json
import re
import threading
from http.server import BaseHTTPRequestHandler
from urllib.parse import parse_qs, urlsplit
from urllib.request import Request, HTTPRedirectHandler, build_opener
from reeldrop_media import extract_payload, normalize, media_url, MediaError, throttle

_proxy_slots=threading.BoundedSemaphore(6)
MEDIA_TYPES={'video/mp4':'mp4','video/webm':'webm','image/jpeg':'jpg','image/png':'png','image/webp':'webp','image/avif':'avif','image/gif':'gif'}

class CDNRedirects(HTTPRedirectHandler):
    def redirect_request(self,req,fp,code,msg,headers,newurl):
        if not media_url(newurl):raise ValueError('Unexpected media destination')
        return super().redirect_request(req,fp,code,msg,headers,newurl)

def select_source(data):
    if data.get('source'):
        target=media_url(data['source'])
        if not target:raise MediaError('Invalid media host.', 'INVALID_MEDIA',400)
        return target
    mode=data.get('mode','all')
    url=normalize(data.get('url'),mode)
    if not url:raise MediaError('Use a public Instagram link.', 'INVALID_URL',400)
    index=int(data.get('index',0));variant=int(data.get('variant',0))
    if not 0<=index<20 or not 0<=variant<10:raise MediaError('Invalid selection.', 'INVALID_SELECTION',400)
    payload=extract_payload(url,mode)
    media=payload['media']
    if index>=len(media):raise MediaError('This media is no longer available.', 'NO_MEDIA',404)
    choices=media[index].get('variants') or [media[index]]
    if variant>=len(choices):raise MediaError('This quality is no longer available.', 'NO_QUALITY',404)
    target=media_url(choices[variant].get('url'))
    if not target:raise MediaError('No downloadable media was found.', 'NO_MEDIA',404)
    return target

class handler(BaseHTTPRequestHandler):
    def error_json(self,status,message,code='DOWNLOAD_FAILED'):
        self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.end_headers()
        self.wfile.write(json.dumps({'error':message,'code':code}).encode())
    def do_GET(self):
        return self.serve_media({k:v[0] for k,v in parse_qs(urlsplit(self.path).query).items()})
    def do_POST(self):
        try:
            length=int(self.headers.get('Content-Length','0'))
            if not 0<length<=16384:raise ValueError()
            data=json.loads(self.rfile.read(length))
            if not isinstance(data,dict):raise ValueError()
        except (ValueError,TypeError):return self.error_json(400,'Invalid download request.','INVALID_REQUEST')
        return self.serve_media(data)
    def serve_media(self,data):
        if self.headers.get('Sec-Fetch-Site')=='cross-site':return self.error_json(403,'Start the download from ReelDrop.','ORIGIN_DENIED')
        acquired=False;started=False
        try:
            throttle(self.headers.get('x-forwarded-for','unknown').split(',')[0]+':asset',90)
            acquired=_proxy_slots.acquire(blocking=False)
            if not acquired:raise MediaError('The downloader is busy. Please retry.','BUSY',429)
            target=select_source(data)
            headers={'User-Agent':'Mozilla/5.0','Referer':'https://www.instagram.com/'}
            requested_range=self.headers.get('Range','')
            if requested_range:
                if not re.fullmatch(r'bytes=\d+-\d*',requested_range):raise MediaError('Invalid byte range.','INVALID_RANGE',416)
                headers['Range']=requested_range
            with build_opener(CDNRedirects()).open(Request(target,headers=headers),timeout=15) as upstream:
                mime=upstream.headers.get('Content-Type','').split(';')[0].strip().lower()
                if mime not in MEDIA_TYPES:raise MediaError('Instagram did not return a supported photo or video.','INVALID_CONTENT',502)
                filename=re.sub(r'[^A-Za-z0-9_-]','',str(data.get('filename','media')))[:80] or 'media'
                disposition='inline' if str(data.get('preview','0'))=='1' else 'attachment'
                status=getattr(upstream,'status',200)
                self.send_response(206 if status==206 else 200)
                self.send_header('Content-Type',mime)
                self.send_header('Content-Disposition',f'{disposition}; filename="ReelDrop-{filename}.{MEDIA_TYPES[mime]}"')
                self.send_header('Cache-Control','no-store');self.send_header('X-Content-Type-Options','nosniff')
                self.send_header('Accept-Ranges','bytes')
                if upstream.headers.get('Content-Length','').isdigit():self.send_header('X-Media-Size',upstream.headers['Content-Length'])
                if upstream.headers.get('Content-Range'):self.send_header('Content-Range',upstream.headers['Content-Range'])
                self.end_headers();started=True
                while chunk:=upstream.read(65536):self.wfile.write(chunk);self.wfile.flush()
        except MediaError as error:
            if not started:self.error_json(error.status,str(error),error.code)
        except (ValueError,TypeError):
            if not started:self.error_json(400,'Invalid download request.','INVALID_REQUEST')
        except Exception:
            if not started:self.error_json(502,'Instagram could not deliver this media. Please try again.')
            else:self.close_connection=True
        finally:
            if acquired:_proxy_slots.release()
