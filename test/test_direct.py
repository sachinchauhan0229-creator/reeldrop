import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

spec = importlib.util.spec_from_file_location('direct', Path(__file__).parents[1] / 'api' / 'direct.py')
direct = importlib.util.module_from_spec(spec)
spec.loader.exec_module(direct)


class DirectTests(unittest.TestCase):
    def test_public_url_validation(self):
        self.assertEqual(direct.normalize('https://instagram.com/reels/ABCDE/?igsh=tracking'), 'https://www.instagram.com/reel/ABCDE/')
        for url in ('https://instagram.com.evil.test/p/ABCDE/', 'http://instagram.com/p/ABCDE/',
                    'https://user:pass@instagram.com/p/ABCDE/', 'https://instagram.com:444/p/ABCDE/',
                    'https://instagram.com/p/ABCDE/extra', 'https://instagram.com/profile/', None):
            self.assertIsNone(direct.normalize(url))

    def test_media_hosts(self):
        self.assertIsNotNone(direct.media_url('https://a.cdninstagram.com/video.mp4'))
        self.assertIsNotNone(direct.media_url('https://a.fbcdn.net/video.mp4'))
        for url in ('https://evil.test/video.mp4', 'https://cdninstagram.com.evil.test/video.mp4',
                    'javascript:alert(1)', 'http://a.fbcdn.net/video.mp4'):
            self.assertIsNone(direct.media_url(url))

    def test_deduplicates_videos_and_rejects_other_hosts(self):
        with patch.object(direct.yt_dlp, 'YoutubeDL') as mock:
            mock.return_value.__enter__.return_value.extract_info.return_value = {'entries': [
                {'url': 'https://a.cdninstagram.com/video.mp4'},
                {'url': 'https://a.cdninstagram.com/video.mp4'},
                {'url': 'https://evil.test/video.mp4'},
            ]}
            self.assertEqual(direct.extract('https://www.instagram.com/p/ABCDE/'), [
                {'url': 'https://a.cdninstagram.com/video.mp4', 'type': 'video'}])


if __name__ == '__main__':
    unittest.main()
