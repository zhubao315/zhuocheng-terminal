#!/usr/bin/env python3
"""从 APK 中定位启动图标资源：manifest android:icon / roundIcon → arsc 反查文件路径。
用法: python find_icon.py <apk>
"""
import struct
import sys
import zipfile


def parse_axml_attrs(raw):
    """遍历 AXML，返回 [(element, {attr_name: (typed_type, typed_data, raw)})]。"""
    # 顶层字符串池
    ftype, fhs, fsize = struct.unpack("<HHI", raw[0:8])
    pool_off = fhs
    rtype, phs, psize = struct.unpack("<HHI", raw[pool_off:pool_off + 8])
    cnt, scnt, flags, sstart, styles = struct.unpack("<IIIII", raw[pool_off + 8:pool_off + 28])
    utf8 = bool(flags & 0x100)
    offs = [struct.unpack("<I", raw[pool_off + 28 + 4 * i:pool_off + 32 + 4 * i])[0] for i in range(cnt)]
    base = pool_off + sstart
    strings = []
    for o in offs:
        p = base + o
        if utf8:
            def rlen(q):
                c = raw[q]
                if c & 0x80:
                    return ((c & 0x7F) << 8) | raw[q + 1], q + 2
                return c, q + 1
            _, p = rlen(p)
            blen, p = rlen(p)
            strings.append(raw[p:p + blen].decode("utf-8", "replace"))
        else:
            ln = struct.unpack("<H", raw[p:p + 2])[0]
            strings.append(raw[p + 2:p + 2 + 2 * ln].decode("utf-16-le", "replace"))

    def rs(i):
        return strings[i] if 0 <= i < len(strings) else None

    out = []
    off = pool_off + psize
    # 跳过 resource map
    while off < len(raw):
        ctype, chs, csize = struct.unpack("<HHI", raw[off:off + 8])
        if ctype == 0x0102:  # start element
            # 节点头 16 字节(type2+hs2+size4+line4+comment4)，其后是 attrExt
            ns, name = struct.unpack("<II", raw[off + 16:off + 24])
            astart, asize, acount, ididx, clsidx, styidx = struct.unpack(
                "<HHHHHH", raw[off + 24:off + 36])
            attrs = {}
            ap = off + 16 + astart
            for i in range(acount):
                ans, aname, araw, ats, atd = struct.unpack("<IIIHH", raw[ap:ap + 16])
                # Res_value: size(2)=ats, res0(1), dataType(1)=atd 高字节, data(4)
                vdata, = struct.unpack("<I", raw[ap + 16:ap + 20])
                vtype = (atd >> 8) & 0xFF
                an = rs(aname) or f"#{aname}"
                attrs[an] = (vtype, vdata, rs(araw) if araw != 0xFFFFFFFF else None)
                ap += asize
            out.append((rs(name), attrs))
        off += csize
    return out


def find_in_arsc(raw, resid):
    """在 resources.arsc 中查 resId → 文件路径。"""
    ttype, ths, tsize = struct.unpack("<HHI", raw[0:8])
    # table 头后可能是全局字符串池（type 0x0001），package 在其后
    off = ths
    ctype, chs, csize = struct.unpack("<HHI", raw[off:off + 8])
    if ctype == 0x0001:
        pkg_off = off + csize
    else:
        pkg_off = ths
    ptype, phs, psize = struct.unpack("<HHI", raw[pkg_off:pkg_off + 8])
    assert ptype == 0x0200, f"不是 package chunk: {hex(ptype)}"
    pkg_id, = struct.unpack("<I", raw[pkg_off + 8:pkg_off + 12])
    typeStrings, = struct.unpack("<I", raw[pkg_off + 268:pkg_off + 272])
    keyStrings, = struct.unpack("<I", raw[pkg_off + 276:pkg_off + 280])
    # 解析两个字符串池
    def pool(off):
        rt, h, sz = struct.unpack("<HHI", raw[off:off + 8])
        cnt, scnt, flags, sstart, styles = struct.unpack("<IIIII", raw[off + 8:off + 28])
        utf8 = bool(flags & 0x100)
        offs = [struct.unpack("<I", raw[off + 28 + 4 * i:off + 32 + 4 * i])[0] for i in range(cnt)]
        base = off + sstart
        arr = []
        for o in offs:
            p = base + o
            if utf8:
                def rlen(q):
                    c = raw[q]
                    if c & 0x80:
                        return ((c & 0x7F) << 8) | raw[q + 1], q + 2
                    return c, q + 1
                _, p = rlen(p)
                blen, p = rlen(p)
                arr.append(raw[p:p + blen].decode("utf-8", "replace"))
            else:
                ln = struct.unpack("<H", raw[p:p + 2])[0]
                arr.append(raw[p + 2:p + 2 + 2 * ln].decode("utf-16-le", "replace"))
        return arr

    type_pool = pool(pkg_off + typeStrings)
    key_pool = pool(pkg_off + keyStrings)

    want_pkg = resid >> 24
    want_type = (resid >> 16) & 0xFF
    want_entry = resid & 0xFFFF

    off = pkg_off + phs
    results = {}
    while off + 16 <= len(raw):
        ctype, chs, csize = struct.unpack("<HHI", raw[off:off + 8])
        if off + csize > len(raw):
            break
        if ctype == 0x0201:  # TYPE chunk
            tid = raw[off + 8]
            res0 = raw[off + 9]
            res1, entryCount, entriesStart = struct.unpack("<HII", raw[off + 10:off + 20])
            if tid == want_type:
                # 偏移表从 chunk 头后 (headerSize) 开始
                offs = [struct.unpack("<I", raw[off + chs + 4 * i:off + chs + 4 * i + 4])[0]
                        for i in range(entryCount)]
                if want_entry < entryCount and offs[want_entry] != 0xFFFFFFFF:
                    ep = off + entriesStart + offs[want_entry]
                    esize, eflags, ekey = struct.unpack("<HHI", raw[ep:ep + 8])
                    # Res_value: size(2) res0(1) dataType(1) data(4)
                    vsize, vres0, vtype = struct.unpack("<HBB", raw[ep + 8:ep + 12])
                    vdata, = struct.unpack("<I", raw[ep + 12:ep + 16])
                    key = key_pool[ekey] if ekey < len(key_pool) else "?"
                    val = type_pool[vdata] if vtype == 0x03 and vdata < len(type_pool) else hex(vdata)
                    results.setdefault(key, []).append((vtype, val))
        off += csize
    return results


def main():
    apk = zipfile.ZipFile(sys.argv[1])
    manifest = apk.read("AndroidManifest.xml")
    elems = parse_axml_attrs(manifest)
    icon_ids = {}
    for el, attrs in elems:
        for an, (t, d, rawv) in attrs.items():
            if an in ("icon", "roundIcon") and t == 1:  # REFERENCE
                icon_ids[an] = d
    print("manifest icon refs:", {k: hex(v) for k, v in icon_ids.items()})
    arsc = apk.read("resources.arsc")
    for k, rid in icon_ids.items():
        print(f"--- {k} = {hex(rid)} ---")
        res = find_in_arsc(arsc, rid)
        for path, vals in res.items():
            print("  ", path, vals)


if __name__ == "__main__":
    main()
