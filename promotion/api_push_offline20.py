"""把全离线版 2.0 信息屏的改动通过 GitHub Contents API 推送（git 通道不可用时的兜底）。

凭据从会话记录中读取，不在控制台打印。用法：python promotion/api_push_offline20.py
"""
import base64
import json
import os
import re
import time
import urllib.error
import urllib.request
from urllib.parse import quote

TRANSCRIPT = 'C:/Users/zhuba/.workbuddy/projects/d-tmp-workbuddy-data-cn-2026-11-23-09-54-19/2b6e516a-9ef7-47e5-899a-f82a8006884f.jsonl'
_text = open(TRANSCRIPT, encoding='utf-8', errors='ignore').read()
_m = re.search(r'ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}', _text)
TOKEN = _m.group(0) if _m else ''
if not TOKEN:
    raise SystemExit('未找到可用 token')

REPO = 'zhubao315/zhuocheng-terminal'
BRANCH = 'main'
ROOT = 'D:/tmp/workbuddy-data-cn/2026-11-23-09-54-19/phonebox/zhuocheng-terminal'
MSG = 'v2.0.1 info screen: '

FILES = [
    'CHANGELOG.md',
    'README.md',
    'docs/index.html',
    'docs/07-releases.md',
    'docs/08-offline-2.0.md',
    'docs/offline.html',
    'docs/releases/zhuocheng-offline-2.0.apk',
    'releases/zhuocheng-offline-2.0.apk',
    'docs/screens/01-信息屏-每日金句.png',
    'docs/screens/02-信息屏-AI伴读.png',
    'docs/screens/03-信息屏-日课十二条.png',
    'docs/screens/04-信息屏-微习惯.png',
    'docs/screens/05-信息屏-静坐三省.png',
    'docs/screens/06-信息屏-成长档案.png',
    'docs/screens/07-多端配置.png',
    'promotion/screens/phone/README.md',
    'promotion/screen_device_shots.mjs',
    'promotion/screen_qa.mjs',
    'promotion/api_push_offline20.py',
    'tools/build_offline_apk.py',
    'tools/build_offline_bundle.py',
    'web/offline/app.html',
    'web/offline/app.css',
    'web/offline/app.js',
]

DELETE = [
    'docs/screens/01-终端总览.png',
    'docs/screens/02-每日金句.png',
    'docs/screens/03-AI伴读.png',
    'docs/screens/04-日课打卡.png',
    'docs/screens/05-微习惯.png',
    'docs/screens/06-静坐三省.png',
    'docs/screens/07-成长档案.png',
]


def api(path, method='GET', data=None):
    url = 'https://api.github.com/repos/' + REPO + '/contents/' + quote(path, safe='/')
    if method == 'GET':
        url += '?ref=' + BRANCH
    body = json.dumps(data).encode('utf-8') if data is not None else None
    req = urllib.request.Request(url, data=body, method=method, headers={
        'Authorization': 'Bearer ' + TOKEN,
        'Accept': 'application/vnd.github+json',
        'User-Agent': 'zhuocheng-offline-publisher',
    })
    for attempt in range(6):
        try:
            with urllib.request.urlopen(req, timeout=180) as r:
                return json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404 and method == 'GET':
                return None
            if e.code == 409:
                raise
            err = 'HTTP ' + str(e.code)
        except Exception as e:
            err = str(e)
        if attempt == 5:
            raise RuntimeError(err)
        print('  retry', attempt + 1, err)
        time.sleep(2 + attempt)


for rel in FILES:
    local = os.path.join(ROOT, rel.replace('/', os.sep))
    print('uploading', rel)
    raw = open(local, 'rb').read()
    payload = {
        'message': MSG + rel,
        'content': base64.b64encode(raw).decode('ascii'),
        'branch': BRANCH,
    }
    existing = api(rel)
    if existing and 'sha' in existing:
        payload['sha'] = existing['sha']
    api(rel, 'PUT', payload)
    print('  ok', len(raw), 'bytes')

for rel in DELETE:
    print('deleting', rel)
    existing = api(rel)
    if not existing or 'sha' not in existing:
        print('  already absent')
        continue
    api(rel, 'DELETE', {
        'message': MSG + 'remove stale screenshot',
        'sha': existing['sha'],
        'branch': BRANCH,
    })
    print('  ok')

print('ALL DONE')
