import unittest

from reeldrop_youtube import MAX_BYTES, available_formats, google_video, youtube_url


class YouTubeTests(unittest.TestCase):
    def test_only_single_youtube_video_links_are_normalized(self):
        video = 'aqz-KE-bpKQ'
        expected = f'https://www.youtube.com/watch?v={video}'
        self.assertEqual(youtube_url(f'youtu.be/{video}?si=secret'), expected)
        self.assertEqual(youtube_url(f'https://www.youtube.com/shorts/{video}'), expected)
        self.assertEqual(youtube_url(expected + '&list=playlist'), expected)
        for url in ('https://youtube.com.evil.test/watch?v=' + video,
                    'https://www.youtube.com/playlist?list=example',
                    'https://www.youtube.com:1234/watch?v=' + video):
            self.assertIsNone(youtube_url(url))

    def test_resolution_requires_audio_and_obeys_size_cap(self):
        cdn = 'https://rr1.googlevideo.com/videoplayback'
        audio = {'url': cdn, 'protocol': 'https', 'ext': 'm4a', 'vcodec': 'none', 'acodec': 'mp4a.40.2', 'filesize': 10}
        video = {'url': cdn, 'protocol': 'https', 'ext': 'mp4', 'vcodec': 'avc1.640028', 'acodec': 'none',
                 'width': 1920, 'height': 1080, 'filesize': 100}
        self.assertEqual(available_formats({'formats': [video]}), {})
        self.assertEqual(available_formats({'formats': [audio, video]}), {1080: [video, audio]})
        self.assertEqual(available_formats({'formats': [audio, dict(video, filesize=MAX_BYTES)]}), {})
        self.assertEqual(available_formats({'formats': [audio, dict(video, url='https://evil.test/videoplayback')]}), {})
        self.assertFalse(google_video('https://rr1.googlevideo.com.evil.test/videoplayback'))
