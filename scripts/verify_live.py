"""Check the public CDN against the exact snapshot produced by this run."""
import json
from pathlib import Path
import time
import urllib.request
import os

BASE = 'https://kibbutz-entrance.github.io/bloomfield-parking/'


def verify():
    expected = json.loads(Path('games.json').read_text())
    suffix = '?verify=' + os.environ.get('GITHUB_RUN_ID', 'manual')
    def get(name):
        request = urllib.request.Request(BASE + name + suffix, headers={'Cache-Control': 'no-cache'})
        with urllib.request.urlopen(request, timeout=20) as response:
            return response.read()
    for attempt in range(6):
        try:
            actual = json.loads(get('games.json'))
            if actual != expected:
                raise ValueError('Public schedule does not match this run snapshot yet')
            for page in ('index.html', 'share.html'):
                html = get(page).decode('utf-8')
                if not all(value in html for value in ('og:title', 'parking-share-v2.jpg', 'parking-logo.png', 'data.js')):
                    raise ValueError('Public page is missing required assets or sharing metadata')
            if not get('parking-logo.png').startswith(b'\x89PNG\r\n\x1a\n'):
                raise ValueError('Public icon is invalid')
            if not get('parking-share-v2.jpg').startswith(b'\xff\xd8\xff'):
                raise ValueError('Public sharing image is invalid')
            print('Verified public website and sharing assets; schedule last_attempt=' + actual['last_attempt'])
            return
        except Exception:
            if attempt == 5:
                raise
            time.sleep(10)


if __name__ == '__main__':
    verify()
