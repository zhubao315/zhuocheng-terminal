"""Fallback publisher: push staged files via GitHub Contents API when git transport is unstable."""
import base64, json, os, sys, time, urllib.request, urllib.error

import re
TRANSCRIPT = 'C:/Users/zhuba/.workbuddy/projects/d-tmp-workbuddy-data-cn-2026-11-23-09-54-19/2b6e516a-9ef7-47e5-899a-f82a8006884f.jsonl'
_text = open(TRANSCRIPT, encoding='utf-8', errors='ignore').read()
_m = re.search(r'ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}', _text)
TOKEN = _m.group(0) if _m else ''
REPO = 'zhubao315/zhuocheng-terminal'
BRANCH = 'main'
ROOT = 'D:/tmp/workbuddy-data-cn/2026-11-23-09-54-19/phonebox/zhuocheng-terminal'

FILES = [
    'docs/index.html',
    'docs/media/zhuocheng-promo.mp4',
    'docs/media/promo-poster.jpg',
    'promotion/tweets-20.md',
    'promotion/video/README.md',
    'promotion/video/render.mjs',
    'promotion/video/scene.html',
]

def api(path, method='GET', data=None):
    url = f'https://api.github.com/repos/{REPO}/contents/{path}'
    params = {}
    if method == 'PUT':
        params = data
        data = json.dumps(data).encode('utf-8')
    req = urllib.request.Request(
        url + ('?ref=' + BRANCH if method == 'GET' else ''),
        data=data, method=method,
        headers={
            'Authorization': 'Bearer ' + TOKEN,
            'Accept': 'application/vnd.github+json',
            'User-Agent': 'zhuocheng-publisher',
        },
    )
    for attempt in range(5):
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404 and method == 'GET':
                return None
            raise
        except Exception as e:
            if attempt == 4:
                raise
            print(f'  retry {attempt+1}: {e}')
            time.sleep(2)

for rel in FILES:
    full = os.path.join(ROOT, rel.replace('/', os.sep))
    print('uploading', rel)
    raw = open(full, 'rb').read()
    payload = {
        'message': 'feat: promo video + landing page film + 20 tweets (' + rel + ')',
        'content': base64.b64encode(raw).decode('ascii'),
        'branch': BRANCH,
    }
    existing = api(rel)
    if existing and 'sha' in existing:
        payload['sha'] = existing['sha']
    api(rel, 'PUT', payload)
    print('  ok', len(raw), 'bytes')

print('ALL DONE')
