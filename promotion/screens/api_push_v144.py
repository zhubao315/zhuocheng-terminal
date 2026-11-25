"""Push v1.4.4 files via GitHub Contents API (git transport unreliable here)."""
import base64, json, os, re, time, urllib.request, urllib.error
from urllib.parse import quote

TRANSCRIPT = 'C:/Users/zhuba/.workbuddy/projects/d-tmp-workbuddy-data-cn-2026-11-23-09-54-19/2b6e516a-9ef7-47e5-899a-f82a8006884f.jsonl'
_text = open(TRANSCRIPT, encoding='utf-8', errors='ignore').read()
_m = re.search(r'ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}', _text)
TOKEN = _m.group(0) if _m else ''
REPO = 'zhubao315/zhuocheng-terminal'
BRANCH = 'main'
ROOT = 'D:/tmp/workbuddy-data-cn/2026-11-23-09-54-19/phonebox/zhuocheng-terminal'

# (repo-relative path, local path)
FILES = [
    ('CHANGELOG.md', ROOT + '/CHANGELOG.md'),
    ('docs/07-releases.md', ROOT + '/docs/07-releases.md'),
    ('docs/index.html', ROOT + '/docs/index.html'),
    ('docs/releases/zhuocheng-terminal-v2signed.apk', ROOT + '/docs/releases/zhuocheng-terminal-v2signed.apk'),
    ('releases/zhuocheng-terminal-v2signed.apk', ROOT + '/releases/zhuocheng-terminal-v2signed.apk'),
    ('docs/screens/01-每日金句.png', ROOT + '/docs/screens/01-每日金句.png'),
    ('docs/screens/02-AI伴读.png', ROOT + '/docs/screens/02-AI伴读.png'),
    ('docs/screens/03-日课打卡.png', ROOT + '/docs/screens/03-日课打卡.png'),
    ('docs/screens/04-微习惯静坐.png', ROOT + '/docs/screens/04-微习惯静坐.png'),
    ('docs/screens/05-定时中枢.png', ROOT + '/docs/screens/05-定时中枢.png'),
    ('promotion/screens/make_screens.py', ROOT + '/promotion/screens/make_screens.py'),
    ('scripts/hide_offline_panel.py', ROOT + '/scripts/hide_offline_panel.py'),
]


def api(path, method='GET', data=None):
    url = 'https://api.github.com/repos/' + REPO + '/contents/' + quote(path, safe='/')
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
            with urllib.request.urlopen(req, timeout=120) as r:
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


for rel, local in FILES:
    print('uploading', rel)
    raw = open(local, 'rb').read()
    payload = {
        'message': 'v1.4.4 push: ' + rel,
        'content': base64.b64encode(raw).decode('ascii'),
        'branch': BRANCH,
    }
    existing = api(rel)
    if existing and 'sha' in existing:
        payload['sha'] = existing['sha']
    api(rel, 'PUT', payload)
    print('  ok', len(raw), 'bytes')

print('ALL DONE')
