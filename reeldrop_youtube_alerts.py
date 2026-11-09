"""Email the ReelDrop administrator when YouTube requests sign-in."""

import json
import logging
import os
import threading
from datetime import datetime, timezone
from http.client import HTTPSConnection, HTTPException

RECONNECT_URL = 'https://reeldrop.jobcraft.in/admin/#youtube-reconnect'
lock = threading.Lock()
last_sent_day = None


def notify_youtube_signin_required():
    global last_sent_day

    if os.environ.get('VERCEL_ENV') != 'production':
        return
    api_key = os.environ.get('RESEND_API_KEY', '').strip()
    sender = os.environ.get('REELDROP_ALERT_FROM', '').strip()
    recipient = os.environ.get('REELDROP_ALERT_TO', '').strip()
    if not (api_key and sender and recipient):
        return

    day = datetime.now(timezone.utc).date()
    if not lock.acquire(blocking=False):
        return
    try:
        if last_sent_day == day:
            return
        payload = json.dumps({
            'from': sender,
            'to': [recipient],
            'subject': 'ReelDrop: YouTube sign-in required',
            'text': 'YouTube asked the ReelDrop downloader to sign in. '
                    'Open your admin dashboard to review the reconnect steps.\n\n'
                    f'Reconnect: {RECONNECT_URL}',
        })
        connection = HTTPSConnection('api.resend.com', timeout=2)
        try:
            connection.request('POST', '/emails', body=payload, headers={
                'Authorization': 'Bearer ' + api_key,
                'Content-Type': 'application/json',
                'Idempotency-Key': f'reeldrop/youtube-signin/{day}',
            })
            with connection.getresponse() as response:
                if 200 <= response.status < 300:
                    last_sent_day = day
                    print('Resend accepted the YouTube reconnect alert', flush=True)
                else:
                    logging.warning('YouTube reconnect alert rejected by Resend (%d)', response.status)
        finally:
            connection.close()
    except (OSError, HTTPException, ValueError):
        logging.warning('YouTube reconnect alert could not reach Resend')
    finally:
        lock.release()
