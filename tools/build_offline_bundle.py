#!/usr/bin/env python3
"""构建全离线版 2.0 单文件应用：把语料、样式、脚本内联进 docs/offline.html。

产物无任何网络依赖：可直接用手机浏览器打开，也可作为 APK 的 WebView 入口。

用法：python tools/build_offline_bundle.py
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TPL = ROOT / 'web' / 'offline' / 'app.html'
CSS = ROOT / 'web' / 'offline' / 'app.css'
JS = ROOT / 'web' / 'offline' / 'app.js'
DATA_DIR = ROOT / 'data'
OUT = ROOT / 'docs' / 'offline.html'


def load_items(name):
    with (DATA_DIR / name).open(encoding='utf-8') as f:
        return json.load(f).get('items', [])


def main():
    payload = {
        'quotes': load_items('quotes.json'),
        'companions': load_items('companion.json'),
        'microhabits': load_items('microhabits.json'),
        'rike': load_items('rike_items.json'),
        'reminders': load_items('rike_reminders.json'),
    }
    data_js = 'window.ZC_DATA=' + json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
    # 避免语料中的 < 或行分隔符提前关闭 script 标签
    data_js = data_js.replace('<', '\\u003c').replace('\u2028', '\\u2028').replace('\u2029', '\\u2029')

    html = TPL.read_text(encoding='utf-8')
    html = html.replace('/*__CSS__*/', CSS.read_text(encoding='utf-8'))
    html = html.replace('/*__DATA__*/', data_js)
    html = html.replace('/*__JS__*/', JS.read_text(encoding='utf-8'))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html, encoding='utf-8')

    print('built', OUT)
    print('items:', ', '.join('%s=%d' % (k, len(v)) for k, v in payload.items()))
    print('size:', OUT.stat().st_size, 'bytes')


if __name__ == '__main__':
    main()
