"""Store a manually connected YouTube session as an encrypted Redis record."""

import argparse
import json
import os
import time
from http.client import HTTPSConnection, HTTPException
from pathlib import Path
from urllib.parse import urlsplit

from cryptography.fernet import Fernet, InvalidToken

SESSION_RECORD = 'reeldrop:youtube:session:v1'
PRODUCTION_SESSION_RECORD = 'reeldrop:youtube:production-session:v1'
MAX_COOKIE_BYTES = 32768


def redis_session(command, token):
    address = urlsplit(os.environ.get('REELDROP_SESSION_REDIS_URL', '').strip())
    if (address.scheme != 'https' or not address.hostname or not address.hostname.endswith('.upstash.io')
            or address.username or address.password or address.port or address.path not in ('', '/')
            or address.query or address.fragment or not token):
        raise ValueError('Configure the Upstash REST URL and token.')

    connection = HTTPSConnection(address.hostname, timeout=4)
    try:
        connection.request('POST', '/', json.dumps(command), {
            'Authorization': 'Bearer ' + token,
            'Content-Type': 'application/json',
        })
        with connection.getresponse() as response:
            if response.status != 200:
                raise ValueError('The session database rejected the request.')
            result = json.loads(response.read(MAX_COOKIE_BYTES * 2))
            if not isinstance(result, dict) or 'result' not in result:
                raise ValueError('The session database returned an invalid response.')
            return result['result']
    finally:
        connection.close()


def session_cipher():
    return Fernet(os.environ.get('REELDROP_SESSION_ENCRYPTION_KEY', '').strip().encode())


def youtube_cookie_text(raw):
    if len(raw) > MAX_COOKIE_BYTES:
        raise ValueError('Use a YouTube-only Netscape cookie file up to 32 KiB.')
    lines = ['# Netscape HTTP Cookie File']
    names = set()
    now = time.time()
    for line in raw.decode('utf-8-sig').splitlines():
        domain, *fields = line.split('\t')
        if len(fields) != 6 or domain.removeprefix('#HttpOnly_').lower() not in (
                'youtube.com', '.youtube.com', 'www.youtube.com'):
            continue
        subdomains, path, secure, expiry, name, value = fields
        expiry = expiry or '0'
        if (subdomains not in ('TRUE', 'FALSE') or secure not in ('TRUE', 'FALSE')
                or not path.startswith('/') or not expiry.isascii() or not expiry.isdecimal()
                or len(expiry) > 12 or (int(expiry) and int(expiry) <= now) or not name or not value):
            continue
        names.add(name)
        lines.append(line)
    if 'LOGIN_INFO' not in names or names.isdisjoint({'SAPISID', '__Secure-1PAPISID', '__Secure-3PAPISID'}):
        raise ValueError('The file does not contain the required active YouTube sign-in cookies.')
    return '\n'.join(lines) + '\n'


def read_youtube_session():
    token = os.environ.get('REELDROP_SESSION_REDIS_READ_TOKEN', '').strip()
    if not (token or os.environ.get('REELDROP_SESSION_REDIS_URL') or os.environ.get('REELDROP_SESSION_ENCRYPTION_KEY')):
        return None
    try:
        cipher = session_cipher()
        record = PRODUCTION_SESSION_RECORD if os.environ.get('VERCEL_ENV') == 'production' else SESSION_RECORD
        encrypted = redis_session(['GET', record], token)
        if not isinstance(encrypted, str):
            raise ValueError('No YouTube session has been uploaded.')
        raw = cipher.decrypt(encrypted.encode('ascii'))
    except (OSError, HTTPException, InvalidToken, ValueError) as error:
        raise RuntimeError('The server could not load its YouTube session.') from error
    return youtube_cookie_text(raw)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('cookie_file', type=Path)
    parser.add_argument('--production', action='store_true', help='Update the Production session record.')
    args = parser.parse_args()
    try:
        with args.cookie_file.open('rb') as source:
            cookies = youtube_cookie_text(source.read(MAX_COOKIE_BYTES + 1))
        encrypted = session_cipher().encrypt(cookies.encode('utf-8')).decode('ascii')
        token = os.environ.get('REELDROP_SESSION_REDIS_WRITE_TOKEN', '').strip()
        record = PRODUCTION_SESSION_RECORD if args.production else SESSION_RECORD
        if redis_session(['SET', record, encrypted], token) != 'OK':
            raise ValueError('The database did not confirm the update.')
    except (OSError, HTTPException, ValueError):
        parser.exit(1, 'Could not save the session. Check the cookie file and private database settings.\n')
    print('Encrypted YouTube session saved.')


if __name__ == '__main__':
    main()
