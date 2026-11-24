#!/usr/bin/env python3
"""拙诚日课 · APK 应用名二进制补丁。

PhoneBox 的启动器名称是 AndroidManifest.xml 二进制 (AXML) 字符串池里的
字面字符串 "PhoneBox"（UTF-16 池）。本工具把该字符串替换为「拙诚日课」，
重建字符串池 chunk，其余字节原样保留——不做任何资源重编译，风险最小。

用法:
  python rebrand_apk.py <in.apk> <out.apk> [新名称]   # 默认名称: 拙诚日课
"""
import struct
import sys
import zipfile
from pathlib import Path

NEW_NAME_DEFAULT = "拙诚日课"
OLD_NAME = "PhoneBox"


def parse_strings(raw, chunk_off):
    rtype, hsize, size = struct.unpack("<HHI", raw[chunk_off:chunk_off + 8])
    assert rtype == 0x0001, f"不是字符串池 chunk: {hex(rtype)}"
    cnt, scnt, flags, sstart, styles = struct.unpack("<IIIII", raw[chunk_off + 8:chunk_off + 28])
    utf8 = bool(flags & 0x100)
    offs = [struct.unpack("<I", raw[chunk_off + 28 + 4 * i:chunk_off + 32 + 4 * i])[0]
            for i in range(cnt)]
    base = chunk_off + sstart
    strings = []
    for o in offs:
        p = base + o
        if utf8:
            def rlen(q):
                c = raw[q]
                if c & 0x80:
                    return ((c & 0x7F) << 8) | raw[q + 1], q + 2
                return c, q + 1
            _, p = rlen(p)          # 解码后字符数
            blen, p = rlen(p)       # UTF-8 字节数
            strings.append(raw[p:p + blen].decode("utf-8", "replace"))
        else:
            ln = struct.unpack("<H", raw[p:p + 2])[0]
            strings.append(raw[p + 2:p + 2 + 2 * ln].decode("utf-16-le", "replace"))
    return strings, flags, size


def build_utf16_pool(strings):
    """重建 UTF-16 字符串池 chunk，返回 bytes。"""
    enc, offs, data = [], [], bytearray()
    for s in strings:
        offs.append(len(data))
        b = s.encode("utf-16-le")
        data += struct.pack("<H", len(s)) + b + b"\x00\x00"
    # 4 字节对齐
    while len(data) % 4:
        data += b"\x00"
    sstart = 28 + 4 * len(strings)
    size = sstart + len(data)
    head = struct.pack("<HHIIIIII", 0x0001, 28, size, len(strings), 0, 0, sstart, 0)
    return head + b"".join(struct.pack("<I", o) for o in offs) + bytes(data)


def patch_manifest(raw, new_name):
    # 顶层 ResFile header
    ftype, fhs, fsize = struct.unpack("<HHI", raw[0:8])
    assert ftype == 0x0003, f"不是 AXML: {hex(ftype)}"
    # 第一个 chunk = 字符串池
    strings, flags, psize = parse_strings(raw, fhs)
    assert not (flags & 0x100), "意外的 UTF-8 池"
    hits = [i for i, s in enumerate(strings) if s == OLD_NAME]
    assert hits, f"manifest 中找不到 {OLD_NAME}"
    for i in hits:
        strings[i] = new_name
    new_pool = build_utf16_pool(strings)
    rest = raw[fhs + psize:]
    new_total = fhs + len(new_pool) + len(rest)
    out = bytearray(raw[:fhs])
    out += new_pool
    out += rest
    struct.pack_into("<I", out, 4, new_total)  # 更新顶层 size
    return bytes(out), len(hits)


def main():
    src, dst = Path(sys.argv[1]), Path(sys.argv[2])
    new_name = sys.argv[3] if len(sys.argv) > 3 else NEW_NAME_DEFAULT
    zin = zipfile.ZipFile(src)
    names = zin.namelist()
    comp = {i.filename: (i.compress_type, i.external_attr, i.create_system) for i in zin.infolist()}
    manifest = zin.read("AndroidManifest.xml")
    patched, nhits = patch_manifest(manifest, new_name)
    print(f"✓ AndroidManifest.xml: 替换 {nhits} 处 {OLD_NAME!r} → {new_name!r}")
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for n in names:
            ctype, attr, csys = comp[n]
            data = patched if n == "AndroidManifest.xml" else zin.read(n)
            zi = zipfile.ZipInfo(n, date_time=(2026, 11, 24, 0, 0, 0))
            zi.compress_type = ctype
            zi.external_attr = attr
            zi.create_system = csys
            zout.writestr(zi, data)
    print(f"✓ 已写出 {dst} ({dst.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
