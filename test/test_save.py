from io import BytesIO
import unittest
from unittest.mock import patch
from api.save import handler, CDNRedirects


def request(path):
    obj = handler.__new__(handler)
    obj.path, obj.headers, obj.wfile = path, {}, BytesIO()
    obj.response_headers = {}
    obj.send_response = lambda code: setattr(obj, 'status', code)
    obj.send_header = lambda key, value: obj.response_headers.update({key: value})
    obj.end_headers = lambda: None
    return obj


class SaveTests(unittest.TestCase):
    def test_rejects_arbitrary_urls_and_bad_indices(self):
        for path in ('/api/save?url=https://evil.test/file', '/api/save?url=https://instagram.com/reel/ABCDE/&index=-1'):
            obj = request(path)
            obj.do_GET()
            self.assertEqual(obj.status, 400)

    def test_blocks_cross_site_download_requests(self):
        obj = request('/api/save?url=https://instagram.com/reel/ABCDE/')
        obj.headers = {'Sec-Fetch-Site': 'cross-site'}
        obj.do_GET()
        self.assertEqual(obj.status, 403)

    def test_streams_attachment_without_buffered_content_length(self):
        obj = request('/api/save?url=https://instagram.com/reel/ABCDE/')
        class Media(BytesIO):
            headers = {'Content-Type': 'video/mp4', 'Content-Length': '200000'}
        with patch('api.save.extract', return_value=[{'url': 'https://a.cdninstagram.com/video.mp4'}]), patch('api.save.build_opener') as opener:
            opener.return_value.open.return_value = Media(b'x' * 200000)
            obj.do_GET()
        self.assertEqual(obj.status, 200)
        self.assertEqual(len(obj.wfile.getvalue()), 200000)
        self.assertNotIn('Content-Length', obj.response_headers)
        self.assertEqual(obj.response_headers['X-Media-Size'], '200000')
        self.assertIn('attachment;', obj.response_headers['Content-Disposition'])

    def test_redirect_cannot_leave_instagram_cdn(self):
        with self.assertRaises(ValueError):
            CDNRedirects().redirect_request(None,None,302,'',{},'https://evil.test/video')

