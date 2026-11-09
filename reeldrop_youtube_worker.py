"""Private transport for ReelDrop's shared YouTube download worker."""

import hmac
import json
import os
from urllib.error import HTTPError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

from reeldrop_media import MediaError
from reeldrop_youtube import MAX_BYTES


class RejectRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def worker_request(url, quality, client):
    endpoint = os.environ.get('REELDROP_YOUTUBE_WORKER_URL', '').strip()
    if not endpoint:
        return None
    token = os.environ.get('REELDROP_YOUTUBE_WORKER_TOKEN', '')
    address = urlsplit(endpoint)
    if (address.scheme != 'https' or not address.hostname or address.username or address.password
            or address.query or address.fragment or address.path != '/api/youtube' or len(token) < 32):
        raise MediaError('The shared YouTube downloader is misconfigured.', 'WORKER_CONFIG', 503)
    body = {'url': url}
    if quality is not None:
        body['quality'] = quality
    request = Request(endpoint, method='POST', data=json.dumps(body).encode(), headers={
        'Authorization': 'Bearer ' + token,
        'Content-Type': 'application/json',
        'X-ReelDrop-Client': hmac.digest(token.encode(), client.encode(), 'sha256').hex(),
    })
    try:
        return build_opener(RejectRedirects()).open(request, timeout=52)
    except HTTPError as error:
        with error:
            if error.code in (400, 413, 422, 429, 502) and error.headers.get_content_type() == 'application/json':
                data = json.loads(error.read(8192))
                raise MediaError(str(data.get('error', 'YouTube download failed.'))[:240],
                                 str(data.get('code', 'WORKER_FAILED'))[:64], error.code) from error
        raise MediaError('The shared YouTube downloader is unavailable.', 'WORKER_UNAVAILABLE', 503) from error
    except OSError as error:
        raise MediaError('The shared YouTube downloader is unavailable.', 'WORKER_UNAVAILABLE', 503) from error


def worker_media_size(response):
    length = response.headers.get('X-Media-Size', '')
    if response.headers.get_content_type() != 'video/mp4' or not length.isdigit() or not 0 < int(length) <= MAX_BYTES:
        raise MediaError('The shared downloader returned an invalid video.', 'WORKER_INVALID_MEDIA', 502)
    return int(length)
