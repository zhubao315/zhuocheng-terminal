#!/usr/bin/env python3
"""在拙诚 APK 中隐藏 PhoneBox 的「电脑未连接 / 点击唤醒」浮层。

PhoneBox 外壳在电脑端不可达时会盖出 #offline 提示与 #wake 唤醒按钮；
对离线优先的拙诚日课终端属于干扰。本脚本只注入 CSS（不改 JS 逻辑），
重建 ZIP 避免重复条目，再用同一密钥 v1+v2 签名。

用法：
    python scripts/hide_offline_panel.py <in.apk> <out-unsigned.apk>
    python scripts/sign_apk_v2.py <out-unsigned.apk> <final.apk>
"""
import sys
import zipfile

CSS_SNIPPET = """

/* ==== Zhuocheng Terminal: offline-first, hide PhoneBox PC-connection chrome ==== */
#offline, #wake { display: none !important; }
body.offline #offline, body.offline #wake { display: none !important; }
"""


def main():
    if len(sys.argv) != 3:
        raise SystemExit(__doc__)
    src, dst = sys.argv[1], sys.argv[2]
    with zipfile.ZipFile(src, 'r') as zin:
        names = zin.namelist()
        css = zin.read('assets/www/style.css').decode('utf-8')
        if 'Zhuocheng Terminal: offline-first' in css:
            print('already patched; copying through')
            with zipfile.ZipFile(dst, 'w') as zout:
                for item in zin.infolist():
                    zout.writestr(item, zin.read(item.filename))
            return
        patched = css + CSS_SNIPPET
        with zipfile.ZipFile(dst, 'w') as zout:
            for item in zin.infolist():
                data = patched.encode('utf-8') if item.filename == 'assets/www/style.css' else zin.read(item.filename)
                zout.writestr(item, data)
    print('patched', dst, 'entries', len(names))


if __name__ == '__main__':
    main()
