from io import BytesIO
import json
import unittest
from unittest.mock import patch
import reeldrop_media as media
from api.save import handler, CDNRedirects, select_source

def request(path):
    obj=handler.__new__(handler);obj.path=path;obj.headers={};obj.wfile=BytesIO();obj.response_headers={}
    obj.send_response=lambda code:setattr(obj,'status',code)
    obj.send_header=lambda key,value:obj.response_headers.update({key:value})
    obj.end_headers=lambda:None
    return obj

class SaveTests(unittest.TestCase):
    def setUp(self):media._requests.clear()
    def test_arbitrary_hosts_and_invalid_indices_fail(self):
        for data in [{'source':'https://evil.test/file.mp4'},{'url':'https://www.instagram.com/p/ABCDE/','index':-1},{'url':'https://127.0.0.1/private'}]:
            with self.assertRaises(media.MediaError):select_source(data)
    def test_redirect_cannot_leave_cdn(self):
        with self.assertRaises(ValueError):CDNRedirects().redirect_request(None,None,302,'',{},'https://evil.test/file')
    def test_post_streams_a_photo_attachment_and_exact_byte_count(self):
        data=json.dumps({'source':'https://a.cdninstagram.com/photo.jpg','filename':'album-photo'}).encode();obj=request('/api/save');obj.headers={'Content-Length':str(len(data))};obj.rfile=BytesIO(data)
        class Asset(BytesIO):headers={'Content-Type':'image/jpeg','Content-Length':'200000'};status=200
        with patch('api.save.build_opener') as opener:opener.return_value.open.return_value=Asset(b'x'*200000);obj.do_POST()
        self.assertEqual(obj.status,200);self.assertEqual(len(obj.wfile.getvalue()),200000);self.assertNotIn('Content-Length',obj.response_headers);self.assertEqual(obj.response_headers['X-Media-Size'],'200000');self.assertIn('.jpg',obj.response_headers['Content-Disposition']);self.assertIn('attachment;',obj.response_headers['Content-Disposition'])
    def test_video_range_is_forwarded_and_streamed(self):
        obj=request('/api/save?source=https%3A%2F%2Fa.cdninstagram.com%2Fvideo.mp4&preview=1');obj.headers={'Range':'bytes=0-1023'}
        class Asset(BytesIO):headers={'Content-Type':'video/mp4','Content-Length':'1024','Content-Range':'bytes 0-1023/5000'};status=206
        with patch('api.save.build_opener') as opener:
            opener.return_value.open.return_value=Asset(b'x'*1024);obj.do_GET();self.assertEqual(opener.return_value.open.call_args.args[0].get_header('Range'),'bytes=0-1023')
        self.assertEqual(obj.status,206);self.assertIn('inline;',obj.response_headers['Content-Disposition']);self.assertEqual(obj.response_headers['Content-Range'],'bytes 0-1023/5000')
    def test_html_response_cannot_be_downloaded_as_media(self):
        obj=request('/api/save?source=https%3A%2F%2Fa.cdninstagram.com%2Ffile')
        class Asset(BytesIO):headers={'Content-Type':'text/html'}
        with patch('api.save.build_opener') as opener:opener.return_value.open.return_value=Asset(b'<script>bad</script>');obj.do_GET()
        self.assertEqual(obj.status,502)
    def test_cross_site_requests_are_denied(self):
        obj=request('/api/save?source=https://a.cdninstagram.com/file');obj.headers={'Sec-Fetch-Site':'cross-site'};obj.do_GET();self.assertEqual(obj.status,403)
