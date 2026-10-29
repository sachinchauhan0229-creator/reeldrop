import json
from io import BytesIO
import unittest
from unittest.mock import patch
from api import direct
import reeldrop_media as media

PHOTO={'pk':'photo1','media_type':1,'image_versions2':{'candidates':[{'url':'https://a.cdninstagram.com/small.jpg','width':320,'height':320},{'url':'https://a.cdninstagram.com/large.jpg','width':1080,'height':1080}]}}
VIDEO={'pk':'video1','media_type':2,'video_versions':[{'url':'https://a.cdninstagram.com/video.mp4','width':720,'height':1280}], 'image_versions2':{'candidates':[{'url':'https://a.cdninstagram.com/cover.jpg','width':720,'height':1280}]}}

class DirectTests(unittest.TestCase):
    def setUp(self):media._cache.clear();media._requests.clear()
    def test_normalizes_only_supported_instagram_inputs(self):
        self.assertEqual(media.normalize('https://instagram.com/reels/ABCDE/?igsh=tracking'),'https://www.instagram.com/reel/ABCDE/')
        self.assertEqual(media.normalize('@creator','viewer'),'https://www.instagram.com/creator/')
        self.assertEqual(media.normalize('https://instagram.com/stories/highlights/123456/','story'),'https://www.instagram.com/stories/highlights/123456/')
        for url in ['https://instagram.com.evil.test/p/ABCDE/','http://instagram.com/p/ABCDE/','https://u:p@instagram.com/p/ABCDE/','https://instagram.com:444/p/ABCDE/','https://instagram.com/p/ABCDE/extra','https://instagram.com/creator/',None]:self.assertIsNone(media.normalize(url))
    def test_cdn_url_validation(self):
        self.assertTrue(media.media_url('https://a.fbcdn.net/file.jpg'))
        for url in ['https://cdninstagram.com.evil.test/file','http://a.fbcdn.net/file','https://user:pass@a.fbcdn.net/file','https://127.0.0.1/file','file:///etc/passwd','javascript:alert(1)']:self.assertIsNone(media.media_url(url))
    def test_mixed_carousel_preserves_order_and_actual_resolutions(self):
        items=media.product_media({'carousel_media':[PHOTO,VIDEO]})
        self.assertEqual([item['type'] for item in items],['image','video'])
        self.assertEqual(items[0]['variants'][0]['width'],1080)
        self.assertEqual(items[0]['variants'][1]['width'],320)
        self.assertEqual(items[1]['thumbnail'],'https://a.cdninstagram.com/cover.jpg')
    def test_video_without_safe_video_url_is_not_replaced_by_its_cover(self):
        self.assertEqual(media.product_media({**VIDEO,'video_versions':[{'url':'https://evil.test/video.mp4'}]}),[])
    def test_sources_without_dimensions_have_distinct_honest_labels(self):
        choices=media.variants([{'url':'https://a.cdninstagram.com/a.jpg'},{'url':'https://a.cdninstagram.com/b.jpg'}],'image')
        self.assertEqual([item['label'] for item in choices],['Source 1 (size not provided)','Source 2 (size not provided)'])
    def test_capture_supports_photo_only_post_and_cache(self):
        class FakeExtractor:
            def extract(self,url):self.products.append({**PHOTO,'user':{'username':'creator'},'caption':{'text':'An original caption'}});return {}
        fake=FakeExtractor()
        with patch.object(media,'CapturePostIE',return_value=fake) as extractor,patch.object(media.yt_dlp,'YoutubeDL'):
            result=media.extract_payload('https://www.instagram.com/p/ABCDE/','photo')
            self.assertEqual(result['media'][0]['type'],'image');self.assertEqual(result['post']['author'],'creator')
            result['media'].clear()
            self.assertEqual(len(media.extract_payload('https://www.instagram.com/p/ABCDE/','photo')['media']),1)
            self.assertEqual(extractor.call_count,1)
    def test_access_failure_is_explicit(self):
        class Blocked:
            def extract(self,url):raise RuntimeError('not available')
        with patch.object(media,'CaptureStoryIE',return_value=Blocked()),patch.object(media.yt_dlp,'YoutubeDL'):
            with self.assertRaises(media.MediaError) as error:media.extract_payload('https://www.instagram.com/stories/creator/123456/','story')
            self.assertEqual(error.exception.code,'STORY_ACCESS_RESTRICTED')
    def test_rest_endpoint_rejects_non_object_json(self):
        obj=direct.handler.__new__(direct.handler);obj.headers={'Content-Length':'2'};obj.rfile=BytesIO(b'[]');obj.wfile=BytesIO();obj.send_response=lambda code:setattr(obj,'status',code);obj.send_header=lambda *args:None;obj.end_headers=lambda:None
        obj.do_POST();self.assertEqual(obj.status,400)

