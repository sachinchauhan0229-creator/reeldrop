"""Resolve and combine public YouTube MP4 streams without exposing CDN URLs."""
import importlib.util
from io import StringIO
import re
import shutil
import subprocess
import time
from pathlib import Path
from urllib.parse import parse_qs, urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

import imageio_ffmpeg
import yt_dlp

from reeldrop_media import MediaError, QuietLogger

VIDEO_ID = re.compile(r'[A-Za-z0-9_-]{11}')
MAX_BYTES = 120 * 1024 * 1024


def youtube_url(value):
    if not isinstance(value, str) or len(value) > 4096:
        return None
    value = value.strip()
    if not re.match(r'^[a-z][a-z0-9+.-]*://', value, re.I):
        value = 'https://' + value
    try:
        parsed = urlsplit(value)
        if parsed.scheme != 'https' or parsed.username or parsed.password or parsed.port:
            return None
        if parsed.hostname == 'youtu.be':
            video = parsed.path.strip('/')
        elif parsed.hostname in ('youtube.com', 'www.youtube.com', 'm.youtube.com'):
            if parsed.path == '/watch':
                video = parse_qs(parsed.query).get('v', [''])[0]
            else:
                parts = parsed.path.strip('/').split('/')
                video = parts[1] if len(parts) == 2 and parts[0] in ('shorts', 'live', 'embed') else ''
        else:
            return None
    except ValueError:
        return None
    return 'https://www.youtube.com/watch?v=' + video if VIDEO_ID.fullmatch(video) else None


def google_video(value):
    try:
        parsed = urlsplit(value)
        return (parsed.scheme == 'https' and parsed.hostname and parsed.hostname.endswith('.googlevideo.com')
                and not (parsed.username or parsed.password or parsed.port)
                and (parsed.path == '/videoplayback' or parsed.path.startswith('/videoplayback/')))
    except (ValueError, TypeError):
        return False


def google_playlist(value):
    try:
        parsed = urlsplit(value)
        return (parsed.scheme == 'https' and parsed.hostname == 'manifest.googlevideo.com'
                and not (parsed.username or parsed.password or parsed.port)
                and parsed.path.startswith('/api/manifest/hls_playlist/'))
    except (ValueError, TypeError):
        return False


def available_formats(info):
    sources = []
    for fmt in reversed(info.get('formats', [])):
        protocol, url = fmt.get('protocol'), fmt.get('url')
        if isinstance(url, str) and ((protocol == 'https' and google_video(url))
                                    or (protocol == 'm3u8_native' and google_playlist(url))):
            sources.append(fmt)
    audio = {}
    for fmt in sources:
        if fmt.get('vcodec') != 'none':
            continue
        if fmt.get('ext') == 'm4a' and (fmt.get('acodec') or '').startswith('mp4a'):
            audio.setdefault('https', fmt)
        if fmt['protocol'] == 'm3u8_native' and fmt.get('format_id') in ('233', '234'):
            audio.setdefault('m3u8_native', fmt)
    selected = {}
    priorities = {}
    for fmt in sources:
        width, height = fmt.get('width') or 0, fmt.get('height') or 0
        quality = min(width, height) if width and height else height
        video_codec, audio_codec = fmt.get('vcodec') or '', fmt.get('acodec') or ''
        if not 0 < quality <= 1080 or fmt.get('ext') != 'mp4' or not video_codec.startswith(('avc1', 'av01', 'hev1', 'hvc1', 'vp09')):
            continue
        extra_audio = audio.get(fmt['protocol']) if audio_codec == 'none' else None
        if not audio_codec.startswith('mp4a') and not extra_audio:
            continue
        pair = [fmt, extra_audio] if extra_audio else [fmt]
        size = sum(stream.get('filesize') or stream.get('filesize_approx') or 0 for stream in pair)
        if not size and info.get('duration') and fmt.get('tbr'):
            size = info['duration'] * (fmt['tbr'] + (128 if extra_audio else 0)) * 125
        if size > MAX_BYTES:
            continue
        priority = (fmt['protocol'] == 'm3u8_native', video_codec.startswith('avc1'))
        if quality not in selected or priority > priorities[quality]:
            selected[quality] = pair
            priorities[quality] = priority
    return dict(sorted(selected.items(), reverse=True))


def node_runtime():
    spec = importlib.util.find_spec('nodejs_wheel')
    if spec and spec.origin:
        bundled = Path(spec.origin).parent / 'bin' / 'node'
        if bundled.is_file():
            return str(bundled)
    return shutil.which('node')


def lookup(url, session=None):
    runtime = node_runtime()
    options = {'quiet': True, 'logger': QuietLogger(), 'noplaylist': True, 'cachedir': False,
               'socket_timeout': 7, 'retries': 0, 'extractor_retries': 0,
               'js_runtimes': {'node': {'path': runtime}} if runtime else {}}
    if session:
        options['cookiefile'] = StringIO(session)
    try:
        with yt_dlp.YoutubeDL(options) as downloader:
            info = downloader.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as error:
        if 'sign in to confirm' in str(error).lower():
            raise MediaError('YouTube requires this server to sign in before it can access the video.',
                             'YOUTUBE_SIGNIN_REQUIRED', 422) from error
        raise MediaError('YouTube did not make this video available to ReelDrop. Try an accessible public video.',
                         'YOUTUBE_UNAVAILABLE', 422) from error
    if not info or info.get('is_live') or info.get('_type') in ('playlist', 'multi_video'):
        raise MediaError('Choose a single finished YouTube video.', 'YOUTUBE_VIDEO_REQUIRED', 422)
    formats = available_formats(info)
    if not formats:
        raise MediaError('No MP4 quality with audio is available within the 120 MB limit for this video.',
                         'YOUTUBE_NO_FORMAT', 422)
    return info, formats


class YouTubeRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        if not (google_video(newurl) or google_playlist(newurl)):
            raise ValueError('Unexpected YouTube media host')
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def fetch_piece(url, output, limit, deadline, headers, opener):
    if not google_video(url):
        raise MediaError('Invalid YouTube media source.', 'YOUTUBE_INVALID_MEDIA', 502)
    if time.monotonic() >= deadline:
        raise TimeoutError('YouTube transfer timed out')
    size = 0
    with opener.open(Request(url, headers=headers), timeout=7) as source:
        expected = source.headers.get('Content-Length', '')
        if expected.isdigit() and int(expected) > limit:
            raise MediaError('This YouTube file exceeds 120 MB. Choose a lower quality.', 'YOUTUBE_TOO_LARGE', 413)
        mime = source.headers.get_content_type()
        if mime not in ('video/mp4', 'audio/mp4', 'video/mp2t', 'audio/aac', 'application/octet-stream'):
            raise MediaError('YouTube did not return an MP4 stream.', 'YOUTUBE_INVALID_MEDIA', 502)
        while chunk := source.read1(65536):
            size += len(chunk)
            if size > limit:
                raise MediaError('This YouTube file exceeds 120 MB. Choose a lower quality.', 'YOUTUBE_TOO_LARGE', 413)
            if time.monotonic() >= deadline:
                raise TimeoutError('YouTube transfer timed out')
            output.write(chunk)
    if not size or (expected.isdigit() and size != int(expected)):
        raise MediaError('The YouTube transfer was interrupted. Try again.', 'YOUTUBE_INCOMPLETE', 502)
    return size


def playlist_pieces(url, headers, opener):
    if not google_playlist(url):
        raise ValueError('Invalid YouTube playlist')
    with opener.open(Request(url, headers=headers), timeout=7) as response:
        body = response.read(262145)
    if len(body) > 262144:
        raise ValueError('YouTube playlist too large')
    lines = body.decode('utf-8').strip().splitlines()
    if not lines or lines[0] != '#EXTM3U' or '#EXT-X-ENDLIST' not in lines:
        raise ValueError('A finished YouTube media playlist is required')
    pieces = []
    for line in lines[1:]:
        if line.startswith(('#EXT-X-BYTERANGE', '#EXT-X-STREAM-INF')) or (
                line.startswith('#EXT-X-KEY:') and line != '#EXT-X-KEY:METHOD=NONE'):
            raise ValueError('Unsupported YouTube playlist')
        if line.startswith('#EXT-X-MAP:'):
            match = re.fullmatch(r'#EXT-X-MAP:URI="([^"]+)"', line)
            if not match:
                raise ValueError('Unsupported initialization segment')
            pieces.append(urljoin(url, match[1]))
        elif line and not line.startswith('#'):
            pieces.append(urljoin(url, line))
    if not 1 <= len(pieces) <= 400 or not all(map(google_video, pieces)):
        raise ValueError('Invalid YouTube media segments')
    return pieces


def download_stream(stream, path, limit, deadline):
    headers = {name: value for name, value in (stream.get('http_headers') or {}).items()
               if name.lower() in ('user-agent', 'accept', 'accept-language', 'origin', 'referer', 'sec-fetch-mode')}
    opener = build_opener(YouTubeRedirects())
    url = stream['url']
    pieces = playlist_pieces(url, headers, opener) if stream['protocol'] == 'm3u8_native' else [url]
    size = 0
    with path.open('wb') as output:
        for piece in pieces:
            size += fetch_piece(piece, output, limit - size, deadline, headers, opener)
    return size


def make_mp4(streams, directory, deadline):
    target = directory / 'download.mp4'
    remaining = MAX_BYTES
    inputs = []
    for index, stream in enumerate(streams):
        if time.monotonic() >= deadline:
            raise TimeoutError('YouTube transfer timed out')
        path = directory / f'stream-{index}.mp4'
        remaining -= download_stream(stream, path, remaining, deadline)
        inputs.extend(['-protocol_whitelist', 'file', '-format_whitelist', 'mov,mpegts,aac', '-i', str(path)])
    command = [imageio_ffmpeg.get_ffmpeg_exe(), '-nostdin', '-v', 'error', *inputs,
               '-map', '0:v:0', '-map', '1:a:0' if len(streams) == 2 else '0:a:0',
               '-c', 'copy', '-movflags', '+faststart', str(target)]
    subprocess.run(command, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                   timeout=max(0.1, deadline - time.monotonic()))
    if target.stat().st_size > MAX_BYTES:
        raise MediaError('This YouTube file exceeds 120 MB. Choose a lower quality.', 'YOUTUBE_TOO_LARGE', 413)
    return target
