#!/usr/bin/env python3
"""在拙诚 APK 中隐藏 PhoneBox 的「电脑未连接 / 点击唤醒 / 离线提示」浮层。

PhoneBox 外壳在电脑端不可达时会盖出 #offline 提示、#wake 唤醒按钮，以及
.offline-msg / .deck-offline::after 等离线占位提示；对离线优先的拙诚日课
终端属于干扰。本脚本只注入 CSS（不改 JS 逻辑，推送/功能完全保留），
重建 ZIP 避免重复条目，再用同一密钥 v1+v2 签名。

用法：
    python scripts/hide_offline_panel.py <in.apk> <out-unsigned.apk> [--force]
    python scripts/sign_apk_v2.py <out-unsigned.apk> <final.apk>
"""
import sys
import zipfile

MARK = 'Zhuocheng Terminal: offline-first'
CSS_SNIPPET = """

/* ==== Zhuocheng Terminal: offline-first, hide PhoneBox PC-connection chrome ==== */
/* status pill + wake button */
#offline, #wake { display: none !important; }
body.offline #offline, body.offline #wake { display: none !important; }
/* in-widget offline placeholders (overview/media/deck) */
.offline-msg, body.offline .offline-msg { display: none !important; }
.deck-offline::after { content: none !important; display: none !important; }
.deck-offline { opacity: 1 !important; }
/* overview clock status: hide red dot + "电脑未连接" text (2nd direct span) + separator */
.status .dot.off { display: none !important; }
.status > span.sep { display: none !important; }
.status > span:nth-of-type(2) { font-size: 0 !important; }
.status > span:nth-of-type(2)::after { content: "离线就绪"; font-size: 11.5px; color: #5eead4; }
"""


def main():
    args = [a for a in sys.argv[1:] if a != '--force']
    force = '--force' in sys.argv
    if len(args) != 2:
        raise SystemExit(__doc__)
    src, dst = args
    with zipfile.ZipFile(src, 'r') as zin:
        names = zin.namelist()
        css = zin.read('assets/www/style.css').decode('utf-8')
        if MARK in css and not force:
            print('already patched; copying through (use --force to re-patch)')
            with zipfile.ZipFile(dst, 'w') as zout:
                for item in zin.infolist():
                    zout.writestr(item, zin.read(item.filename))
            return
        if MARK in css and force:
            # strip previous injected block
            idx = css.find('/* ==== Zhuocheng Terminal: offline-first')
            if idx >= 0:
                css = css[:idx]
        patched = css + CSS_SNIPPET
        with zipfile.ZipFile(dst, 'w') as zout:
            for item in zin.infolist():
                data = patched.encode('utf-8') if item.filename == 'assets/www/style.css' else zin.read(item.filename)
                zout.writestr(item, data)
    print('patched', dst, 'entries', len(names), 'force', force)


if __name__ == '__main__':
    main()
