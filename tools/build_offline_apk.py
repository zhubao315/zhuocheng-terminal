#!/usr/bin/env python3
"""把全离线 2.0 单文件应用装入 PhoneBox 基座 APK。

只替换 assets/www/index.html（WebView 入口），保留包名、图标、品牌资源和签名身份。
产物为未签名 APK，随后用 scripts/sign_apk_v2.py 做 v1+v2 双签。

用法：
    python tools/build_offline_apk.py <base.apk> <out-unsigned.apk> [docs/offline.html]
"""
import sys
import zipfile
from pathlib import Path

ENTRY = 'assets/www/index.html'


def main():
    args = sys.argv[1:]
    if len(args) not in (2, 3):
        raise SystemExit(__doc__)
    src, dst = args[0], args[1]
    html_path = Path(args[2]) if len(args) == 3 else Path(__file__).resolve().parent.parent / 'docs' / 'offline.html'
    html = html_path.read_bytes()

    with zipfile.ZipFile(src, 'r') as zin, zipfile.ZipFile(dst, 'w') as zout:
        names = zin.namelist()
        if ENTRY not in names:
            raise SystemExit('base apk 缺少 ' + ENTRY)
        for item in zin.infolist():
            data = html if item.filename == ENTRY else zin.read(item.filename)
            zout.writestr(item, data)

    print('built', dst)
    print('entries', len(names), 'html', len(html), 'bytes from', html_path)


if __name__ == '__main__':
    main()
