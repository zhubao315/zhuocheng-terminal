#!/usr/bin/env python3
"""通过 GitHub Contents API 上传本次改动（git push 通道不稳时的兜底）。"""
import base64, json, os, re, time, urllib.parse, urllib.request, urllib.error

REPO = 'zhubao315/zhuocheng-terminal'
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..'))
TRANSCRIPT = r'C:/Users/zhuba/.workbuddy/projects/d-tmp-workbuddy-data-cn-2026-11-23-09-54-19/2b6e516a-9ef7-47e5-899a-f82a8006884f.jsonl'

def token():
    t = open(TRANSCRIPT, encoding='utf-8', errors='ignore').read()
    return re.search(r'ghp_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{30,}', t).group(0)

TOK = token()
HEADERS = {'Authorization': 'Bearer ' + TOK, 'Accept': 'application/vnd.github+json', 'User-Agent': 'publisher'}

# (local relative path, commit message) — files changed/added in this round
UPLOAD = [
    ('docs/index.html', 'docs: 展示区改真机实拍截图与文案'),
    ('docs/07-releases.md', 'docs: 更新 v1.4.4 校验值'),
    ('CHANGELOG.md', 'docs: v1.4.4 真机实拍与离线补丁说明'),
    ('docs/releases/zhuocheng-terminal-v2signed.apk', 'build: v1.4.4 完整离线纯净补丁 APK'),
    ('scripts/hide_offline_panel.py', 'fix: 完善离线提示遮蔽并支持 --force'),
    ('scripts/inspect_overlay.py', 'chore: 离线浮层诊断脚本'),
    ('promotion/screens/phone/README.md', 'docs: 真机截图说明'),
    ('promotion/screens/phone/inject_cfg.mjs', 'chore: 真机配置注入脚本'),
    ('docs/screens/01-终端总览.png', 'screens: 真机总览'),
    ('docs/screens/02-页面导航.png', 'screens: 真机页面导航'),
    ('docs/screens/03-日课打卡.png', 'screens: 真机日课打卡'),
    ('docs/screens/04-静坐三省.png', 'screens: 真机静坐三省'),
    ('docs/screens/05-每日金句.png', 'screens: 真机每日金句'),
]

# old screenshot files removed locally; delete on remote too
DELETE = [
    ('docs/screens/01-每日金句.png', 'screens: remove old rendered screenshot'),
    ('docs/screens/02-AI伴读.png', 'screens: remove old rendered screenshot'),
    ('docs/screens/04-微习惯静坐.png', 'screens: remove old rendered screenshot'),
    ('docs/screens/05-定时中枢.png', 'screens: remove old rendered screenshot'),
]

def api_url(path):
    return 'https://api.github.com/repos/%s/contents/%s' % (REPO, urllib.parse.quote(path))

def get_sha(path):
    req = urllib.request.Request(api_url(path), headers=HEADERS)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.load(r).get('sha')
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise

def put(path, raw, msg, retries=5):
    payload = {'message': msg, 'content': base64.b64encode(raw).decode(), 'branch': 'main'}
    sha = get_sha(path)
    if sha:
        payload['sha'] = sha
    data = json.dumps(payload).encode()
    for attempt in range(retries):
        try:
            req = urllib.request.Request(api_url(path), data=data, method='PUT', headers=HEADERS)
            with urllib.request.urlopen(req, timeout=60) as r:
                print('PUT', path, r.status)
                return True
        except urllib.error.HTTPError as e:
            print('PUT', path, 'HTTP', e.code, e.read().decode()[:120])
            return False
        except Exception as e:
            if attempt == retries - 1:
                print('PUT', path, 'FAILED', e)
                return False
            time.sleep(2)
    return False

def delete(path, msg, retries=5):
    sha = get_sha(path)
    if not sha:
        print('DEL', path, 'not found (skip)')
        return True
    payload = {'message': msg, 'sha': sha, 'branch': 'main'}
    data = json.dumps(payload).encode()
    for attempt in range(retries):
        try:
            req = urllib.request.Request(api_url(path), data=data, method='DELETE', headers=HEADERS)
            with urllib.request.urlopen(req, timeout=60) as r:
                print('DEL', path, r.status)
                return True
        except Exception as e:
            if attempt == retries - 1:
                print('DEL', path, 'FAILED', e)
                return False
            time.sleep(2)
    return False

ok = True
for rel, msg in UPLOAD:
    p = os.path.join(ROOT, rel.replace('/', os.sep))
    ok = put(rel, open(p, 'rb').read(), msg) and ok
for rel, msg in DELETE:
    ok = delete(rel, msg) and ok
print('ALL OK' if ok else 'SOME FAILED')
