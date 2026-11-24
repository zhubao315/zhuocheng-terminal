#!/usr/bin/env python3
"""拙诚日课 APK 一键构建：改名 + 换图标 + v1 签名素材（未签名输出）。

对 PhoneBox base APK 做最小二进制补丁：
  1. AndroidManifest.xml 字符串池: "PhoneBox" → "拙诚日课"（复用 rebrand_apk.patch_manifest）
  2. resources.arsc 原地 4 字节补丁:
     - ic_launcher_fg (0x7f050000) 的值 res/Ki.xml → res/J5.png（自适应图标前景）
     - ic_tile 的 anydpi 值 res/a7.xml → res/J5.png（legacy 图标配置）
  3. PNG 字节替换:
     - J5.png → 432×432 透明底「拙」字形（自适应前景 + legacy 图标）
     - kL/Ji/HM/tg/Br.png → 圆角深底完整图标（tile/通知）

用法: python build_zhuocheng_apk.py <base.apk> <out_unsigned.apk>
"""
import struct
import sys
import zipfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from rebrand_apk import patch_manifest  # noqa: E402

NEW_LABEL = "拙诚日课"
OLD_FG_KEY = "ic_launcher_fg"
NEW_FG_PATH = "res/J5.png"
LEGACY_OLD_PATH = "res/a7.xml"

BG = (15, 19, 24, 255)        # #0f1318 深墨
TEAL = (45, 212, 191, 255)    # #2dd4bf
GOLD = (245, 158, 11, 255)    # #f59e0b
FONT_CANDIDATES = [
    "C:/Windows/Fonts/msyhbd.ttc",   # 雅黑粗体
    "C:/Windows/Fonts/msyh.ttc",
    "C:/Windows/Fonts/simhei.ttf",
]


def find_font():
    from PIL import ImageFont
    for f in FONT_CANDIDATES:
        if Path(f).exists():
            return f
    raise RuntimeError("找不到中文字体")


def make_glyph(size):
    """透明底居中「拙」字形。"""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    fs = int(size * 0.56)
    font = ImageFont.truetype(find_font(), fs)
    bbox = d.textbbox((0, 0), "拙", font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1]), "拙",
           font=font, fill=TEAL)
    # 右下金点，呼应日课打卡
    r = int(size * 0.035)
    cx, cy = int(size * 0.70), int(size * 0.70)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=GOLD)
    return img


def make_full(size):
    """圆角深底完整图标（tile / 通知用）。"""
    from PIL import Image, ImageDraw, ImageFont
    img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    rad = int(size * 0.22)
    d.rounded_rectangle((0, 0, size - 1, size - 1), radius=rad, fill=BG)
    fs = int(size * 0.52)
    font = ImageFont.truetype(find_font(), fs)
    bbox = d.textbbox((0, 0), "拙", font=font)
    w, h = bbox[2] - bbox[0], bbox[3] - bbox[1]
    d.text(((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1] - size * 0.02),
           "拙", font=font, fill=TEAL)
    r = int(size * 0.03)
    cx, cy = int(size * 0.68), int(size * 0.66)
    d.ellipse((cx - r, cy - r, cx + r, cy + r), fill=GOLD)
    return img


def parse_global_strings(arsc):
    """解析全局值字符串池，返回 [字符串]。"""
    o = 12
    rt, hh, ss = struct.unpack("<HHI", arsc[o:o + 8])
    cnt, scnt, flags, sstart, styles = struct.unpack("<IIIII", arsc[o + 8:o + 28])
    utf8 = bool(flags & 0x100)
    offs = [struct.unpack("<I", arsc[o + 28 + 4 * i:o + 32 + 4 * i])[0] for i in range(cnt)]
    base = o + sstart
    arr = []
    for off in offs:
        p = base + off

        def rl(q):
            c = arsc[q]
            if c & 0x80:
                return ((c & 0x7F) << 8) | arsc[q + 1], q + 2
            return c, q + 1
        if utf8:
            _, p = rl(p)
            bl, p = rl(p)
            arr.append(arsc[p:p + bl].decode("utf-8", "replace"))
        else:
            ln = struct.unpack("<H", arsc[p:p + 2])[0]
            arr.append(arsc[p + 2:p + 2 + 2 * ln].decode("utf-16-le", "replace"))
    return arr


def patch_arsc(arsc, want_keys):
    """原地改 Res_value：want_keys = {key: (新字符串索引, 匹配旧值索引或 None)}。
    匹配旧值非 None 时只改值相同的条目；None 时只改第一条命中。返回 arsc bytes 与日志。"""
    pkg_off = 28244
    phs, = struct.unpack("<H", arsc[pkg_off + 2:pkg_off + 4])
    gk = parse_global_strings(arsc)

    def pool(off):
        rt, hh, ss = struct.unpack("<HHI", arsc[off:off + 8])
        cnt, scnt, flags, sstart, styles = struct.unpack("<IIIII", arsc[off + 8:off + 28])
        utf8 = bool(flags & 0x100)
        offs = [struct.unpack("<I", arsc[off + 28 + 4 * i:off + 32 + 4 * i])[0] for i in range(cnt)]
        base = off + sstart
        arr = []
        for oo in offs:
            p = base + oo
            if utf8:
                def rl(q):
                    c = arsc[q]
                    if c & 0x80:
                        return ((c & 0x7F) << 8) | arsc[q + 1], q + 2
                    return c, q + 1
                _, p = rl(p)
                bl, p = rl(p)
                arr.append(arsc[p:p + bl].decode("utf-8", "replace"))
            else:
                ln = struct.unpack("<H", arsc[p:p + 2])[0]
                arr.append(arsc[p + 2:p + 2 + 2 * ln].decode("utf-16-le", "replace"))
        return arr
    kk = pool(pkg_off + 548)
    buf = bytearray(arsc)
    done = {}
    off = pkg_off + phs
    while off + 16 <= len(buf):
        t, hs, sz = struct.unpack("<HHI", buf[off:off + 8])
        if sz < 8 or off + sz > len(buf):
            break
        if t == 0x0201:
            res1, ecnt, estart = struct.unpack("<HII", buf[off + 10:off + 20])
            for i in range(ecnt):
                ot = struct.unpack("<I", buf[off + hs + 4 * i:off + hs + 4 * i + 4])[0]
                if ot == 0xFFFFFFFF:
                    continue
                ep = off + estart + ot
                _, _, ekey = struct.unpack("<HHI", buf[ep:ep + 8])
                key = kk[ekey] if ekey < len(kk) else ""
                spec = want_keys.get(key)
                if spec is None:
                    continue
                new_idx, match_old = spec
                vdata_off = ep + 12
                old, = struct.unpack("<I", buf[vdata_off:vdata_off + 4])
                if match_old is not None and old != match_old:
                    continue
                if key in done:
                    continue
                buf[vdata_off:vdata_off + 4] = struct.pack("<I", new_idx)
                done[key] = (gk[old] if old < len(gk) else hex(old),
                             gk[new_idx] if new_idx < len(gk) else hex(new_idx))
        off += sz
    return bytes(buf), done


def main():
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    zin = zipfile.ZipFile(src)
    manifest = zin.read("AndroidManifest.xml")
    patched_m, nhits = patch_manifest(manifest, NEW_LABEL)
    print(f"✓ manifest: 应用名 → {NEW_LABEL}（{nhits} 处）")

    arsc = zin.read("resources.arsc")
    gk = parse_global_strings(arsc)
    idx_j5 = gk.index(NEW_FG_PATH)
    idx_a7 = gk.index(LEGACY_OLD_PATH)
    arsc2, done = patch_arsc(arsc, {
        OLD_FG_KEY: (idx_j5, None),      # 自适应图标前景 → J5.png
        "ic_tile": (idx_j5, idx_a7),     # 仅 a7.xml 那条 anydpi 配置 → J5.png
    })
    print(f"✓ arsc 原地补丁: {done}")
    n_a7 = sum(1 for o, n in done.values() if o == LEGACY_OLD_PATH)
    if n_a7 == 0:
        print("⚠ ic_tile 的 a7.xml 条目未命中（legacy 图标未改，只影响极老 launcher）")

    comp = {i.filename: (i.compress_type, i.external_attr, i.create_system) for i in zin.infolist()}
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for n in zin.namelist():
            ctype, attr, csys = comp[n]
            zi = zipfile.ZipInfo(n, date_time=(2026, 11, 24, 0, 0, 0))
            zi.compress_type = ctype
            zi.external_attr = attr
            zi.create_system = csys
            if n == "AndroidManifest.xml":
                data = patched_m
            elif n == "resources.arsc":
                data = arsc2
            elif n == "res/J5.png":
                data = b""
                make_glyph(432).save(dst.parent / "_tmp_J5.png")
                data = (dst.parent / "_tmp_J5.png").read_bytes()
                (dst.parent / "_tmp_J5.png").unlink()
            elif n in ("res/kL.png", "res/Ji.png"):
                data = b""
                make_full(64).save(dst.parent / "_tmp.png")
                data = (dst.parent / "_tmp.png").read_bytes()
                (dst.parent / "_tmp.png").unlink()
            elif n == "res/HM.png":
                data = b""
                make_full(96).save(dst.parent / "_tmp.png")
                data = (dst.parent / "_tmp.png").read_bytes()
                (dst.parent / "_tmp.png").unlink()
            elif n in ("res/tg.png", "res/Br.png"):
                data = b""
                make_full(192).save(dst.parent / "_tmp.png")
                data = (dst.parent / "_tmp.png").read_bytes()
                (dst.parent / "_tmp.png").unlink()
            else:
                data = zin.read(n)
            zout.writestr(zi, data)
    print(f"✓ 已写出 {dst} ({dst.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
