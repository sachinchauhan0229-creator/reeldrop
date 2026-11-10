import unittest
from unittest.mock import patch

from reeldrop_facebook import extract_facebook, facebook_url, resolve_share


class FacebookTest(unittest.TestCase):
    def test_normalizes_only_facebook_video_links(self):
        self.assertEqual(facebook_url('www.facebook.com/example/videos/123456/?tracking=1'),
                         'https://www.facebook.com/watch/?v=123456')
        self.assertEqual(facebook_url('https://www.facebook.com/reel/123456/'),
                         'https://m.facebook.com/watch/?v=123456&_rdr')
        for url in ('https://www.facebook.com.evil.test/watch?v=123456',
                    'https://www.facebook.com@evil.test/reel/123456',
                    'https://www.facebook.com:444/reel/123456',
                    'https://www.facebook.com/l.php?u=https://evil.test',
                    'https://www.facebook.com/watch?v=123456&v=999999'):
            with self.subTest(url=url):
                self.assertIsNone(facebook_url(url))

    @patch('reeldrop_facebook.build_opener')
    def test_share_redirect_rejects_external_destination(self, build_opener):
        open_url = build_opener.return_value.open
        response = open_url.return_value.__enter__.return_value
        response.headers = {'Location': 'https://evil.test/watch?v=123456'}
        with self.assertRaises(ValueError):
            resolve_share('https://fb.watch/video123/')
        open_url.assert_called_once()

    @patch('reeldrop_facebook.FacebookIE')
    def test_only_progressive_facebook_cdn_formats_are_exposed(self, extractor):
        cdn = 'https://video.example.fbcdn.net/'
        extractor.return_value.extract.return_value = {
            'id': '123456', 'title': 'A video',
            'formats': [
                {'format_id': 'sd', 'url': cdn + 'sd.mp4'},
                {'format_id': 'hd', 'url': cdn + 'hd.mp4'},
                {'ext': 'mp4', 'url': cdn + 'silent.mp4', 'acodec': 'none'},
                {'ext': 'mp4', 'url': 'https://evil.test/movie.mp4'},
            ],
        }
        result = extract_facebook('https://www.facebook.com/watch/?v=123456')
        self.assertEqual([v['label'] for v in result['media'][0]['variants']], ['HD', 'SD'])
        self.assertEqual(result['media'][0]['url'], cdn + 'hd.mp4')
