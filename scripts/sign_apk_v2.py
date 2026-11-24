#!/usr/bin/env python3
"""拙诚日课终端 APK 签名器 v2 —— v1(JAR) + v2(APK Signature Scheme v2) 双签名。

背景：Android 11+ 强制要求 targetSdk>=30 的应用携带 v2 签名，
v1-only 的包在新系统上安装报「解析软件包时出现问题(33) packageInfo is null」。
本脚本用同一密钥完成 v1 + v2 双签，并在 keys/ 下持久化密钥
（后续版本更新复用同一签名，避免卸载重装）。

用法：
    python sign_apk_v2.py <in.apk> <out.apk>          # 自动加载/生成密钥
    python sign_apk_v2.py --verify <signed.apk>       # 校验 v2 块与摘要

v2 实现依据 Android 官方规范：
- 签名块插在 ZIP 条目区与 Central Directory 之间，magic "APK Sig Block 42"
- 内容摘要：三段（条目区/CD/EOCD-with-updated-offset）按 1MB 分块，
  每块 SHA256(0xa5||chunk)，最终 SHA256(0x5a||le64(total)||chunks...)
- 算法 ID 0x0103 = RSASSA-PKCS1-v1_5 + SHA2-256
"""
import base64
import datetime
import hashlib
import os
import re
import struct
import sys
import zipfile

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding, rsa
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives.serialization import pkcs7

ALG_RSA_PKCS1_SHA256 = 0x0103
CHUNK_SIZE = 1024 * 1024          # 1MB
V2_BLOCK_ID = 0x7109871a
MAGIC = b"APK Sig Block 42"

KEY_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".keys")
KEY_PEM = os.path.join(KEY_DIR, "signer_key.pem")
CERT_PEM = os.path.join(KEY_DIR, "signer_cert.pem")


# ---------------------------------------------------------------- keys
def load_or_create_keys():
    os.makedirs(KEY_DIR, exist_ok=True)
    if os.path.exists(KEY_PEM) and os.path.exists(CERT_PEM):
        key = serialization.load_pem_private_key(open(KEY_PEM, "rb").read(), password=None)
        cert = x509.load_pem_x509_certificate(open(CERT_PEM, "rb").read())
        print("keys loaded:", KEY_DIR)
        return key, cert
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, u"ZhuoCheng Terminal"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"ZhuoCheng Daily"),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (x509.CertificateBuilder()
            .subject_name(name).issuer_name(name)
            .public_key(key.public_key())
            .serial_number(x509.random_serial_number())
            .not_valid_before(now - datetime.timedelta(days=1))
            .not_valid_after(now + datetime.timedelta(days=7300))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .sign(key, hashes.SHA256()))
    open(KEY_PEM, "wb").write(key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
    open(CERT_PEM, "wb").write(cert.public_bytes(serialization.Encoding.PEM))
    print("keys generated & saved:", KEY_DIR)
    return key, cert


# ---------------------------------------------------------------- v1
def b64(data: bytes) -> str:
    return base64.b64encode(hashlib.sha256(data).digest()).decode()


def _mf_entry(name: str, data: bytes) -> bytes:
    return (f"Name: {name}\r\nSHA-256-Digest: {b64(data)}\r\n\r\n").encode()


def v1_sign(src: str, dst: str, key, cert):
    """v1(JAR) 签名：重写 zip 并注入 MANIFEST.MF / CERT.SF / CERT.RSA。"""
    zin = zipfile.ZipFile(src)
    entries = [i for i in zin.infolist()
               if not re.match(r"^META-INF/.*\.(SF|RSA|DSA|EC)$", i.filename)]
    mf = bytearray(b"Manifest-Version: 1.0\r\nCreated-By: 1.0 (ZhuoCheng)\r\n\r\n")
    for item in entries:
        if item.filename != "META-INF/MANIFEST.MF":
            mf += _mf_entry(item.filename, zin.read(item.filename))
    mf = bytes(mf)
    sf = bytearray(b"Signature-Version: 1.0\r\nCreated-By: 1.0 (ZhuoCheng)\r\n\r\n")
    for item in entries:
        if item.filename != "META-INF/MANIFEST.MF":
            sf += _mf_entry(item.filename, zin.read(item.filename))
    sf = bytes(sf)
    pk7 = (pkcs7.PKCS7SignatureBuilder()
           .set_data(sf)
           .add_signer(cert, key, hashes.SHA256())
           .sign(serialization.Encoding.DER,
                 [pkcs7.PKCS7Options.DetachedSignature, pkcs7.PKCS7Options.Binary,
                  pkcs7.PKCS7Options.NoCapabilities]))
    with zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED) as zout:
        for item in entries:
            if item.filename == "META-INF/MANIFEST.MF":
                zout.writestr("META-INF/MANIFEST.MF", mf)
            else:
                zout.writestr(item, zin.read(item.filename))
        zout.writestr("META-INF/CERT.SF", sf)
        zout.writestr("META-INF/CERT.RSA", pk7)
    zin.close()


# ---------------------------------------------------------------- v2
def _lp(b: bytes) -> bytes:
    return struct.pack("<I", len(b)) + b


def chunked_sha256(sections):
    """按 v2 规范计算内容摘要（与 apksig/apksigtool 实测一致）：
    - 段内分块（不跨段），每块摘要 = SHA256(0xa5 || u32(块长) || 块)
    - 顶层摘要 = SHA256(0x5a || u32(块数) || 各块摘要依次拼接)
    """
    digests = []
    for sec in sections:
        for i in range(0, len(sec), CHUNK_SIZE):
            chunk = sec[i:i + CHUNK_SIZE]
            digests.append(hashlib.sha256(
                b"\xa5" + struct.pack("<I", len(chunk)) + chunk).digest())
    md = hashlib.sha256(b"\x5a" + struct.pack("<I", len(digests)) + b"".join(digests))
    return md.digest()


def find_zip_sections(data: bytes):
    """返回 (cd_start, eocd_off, eocd)。要求 EOCD 无注释。"""
    eocd_off = data.rfind(b"PK\x05\x06")
    if eocd_off < 0:
        raise RuntimeError("EOCD not found")
    eocd = bytearray(data[eocd_off:])
    cd_size = struct.unpack_from("<I", eocd, 12)[0]
    cd_off = struct.unpack_from("<I", eocd, 16)[0]
    comment_len = struct.unpack_from("<H", eocd, 20)[0]
    if comment_len != 0:
        raise RuntimeError("EOCD with comment not supported")
    if cd_off + cd_size != eocd_off:
        raise RuntimeError(f"zip layout unexpected: cd_off({cd_off})+size({cd_size}) != eocd({eocd_off})")
    return cd_off, eocd_off, eocd


def build_v2_block(data: bytes, key, cert):
    """构造 v2 签名块字节串（待插入 CD 之前）。

    布局（与 apksig/AOSP 解析器实测一致）：
    - EOCD 的 CD-offset 指向【真实 Central Directory】（签名块插在其前面，
      验证器从 CD 前 24 字节 footer [u64 size][magic] 反向定位签名块）
    - 摘要三段：条目区 / 真实CD / EOCD（原样，其 offset 已指向真实 CD）
    - v2 value = u32(len) signers_blob
      signers_blob = u32(len) signer
      signer = u32(len) signedData + u32(len) signaturesSeq + u32(len) publicKey
      signedData = u32(len) digestsSeq + u32(len) certsSeq + u32(len) attrsSeq
      digestsSeq / signaturesSeq 的每条记录 = u32(recLen) + u32(alg) + u32(len) + data
    """
    cd_start, eocd_off, eocd = find_zip_sections(data)

    # 先估算块长（块长不依赖 EOCD 内容，迭代一次即收敛）
    blk = 1500
    for _ in range(3):
        real_cd = cd_start + blk
        # 段 3 = EOCD（offset 指向【签名块起点】= 原 CD 位置，即插入前的原始值；
        # 文件里的 EOCD 虽指向真实 CD，但摘要计算用的是"插入前"的 EOCD——apksig 惯例）
        eocd_iter = bytes(eocd)  # 原 EOCD：offset 就是 cd_start
        # 段 2 是完整的原始 CD（插入块后 CD 整体右移，内容不变）
        sections = [data[:cd_start], data[cd_start:eocd_off], eocd_iter]
        content_digest = chunked_sha256(sections)

        digests_seq = (struct.pack('<I', 4 + 4 + len(content_digest))
                       + struct.pack('<I', ALG_RSA_PKCS1_SHA256)
                       + struct.pack('<I', len(content_digest))
                       + content_digest)                       # 单条记录
        # certificates 元素 = [总长][[单证书长][DER]...]——每张证书自带长度前缀
        certs_elem = _lp(cert.public_bytes(serialization.Encoding.DER))
        signed_data = _lp(digests_seq) + _lp(certs_elem) + _lp(b"")

        signature = key.sign(signed_data, padding.PKCS1v15(), hashes.SHA256())
        sig_record = (struct.pack('<I', 4 + 4 + len(signature))
                      + struct.pack('<I', ALG_RSA_PKCS1_SHA256)
                      + struct.pack('<I', len(signature))
                      + signature)
        public_key = key.public_key().public_bytes(
            serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)

        signer = _lp(signed_data) + _lp(sig_record) + _lp(public_key)
        v2_value = _lp(_lp(signer))

        id_val = struct.pack("<I", V2_BLOCK_ID) + v2_value
        pair = struct.pack("<Q", len(id_val)) + id_val
        size = len(pair) + 8 + 16
        block = struct.pack("<Q", size) + pair + struct.pack("<Q", size) + MAGIC
        if len(block) == blk:
            break
        blk = len(block)

    # EOCD 的 CD-offset 改为真实 CD 位置
    eocd_mod = bytearray(eocd)
    struct.pack_into("<I", eocd_mod, 16, cd_start + len(block))
    return block, cd_start, eocd_off, bytes(eocd_mod)


def v2_sign_file(path: str, key, cert):
    data = open(path, "rb").read()
    block, cd_start, eocd_off, eocd = build_v2_block(data, key, cert)
    out = data[:cd_start] + block + data[cd_start:eocd_off] + bytes(eocd)
    open(path, "wb").write(out)
    print(f"v2 block appended: {len(block)} bytes, CD {cd_start} -> {cd_start + len(block)}")
    return out


# ---------------------------------------------------------------- verify
def verify_v2(path: str, key, cert):
    """自校验：按 Android 实际布局解析，重算三段摘要 + RSA 验签。"""
    from cryptography.hazmat.primitives import serialization as _ser
    data = open(path, "rb").read()
    magic_pos = data.rfind(MAGIC)
    assert magic_pos > 0, "v2 magic not found"
    size2 = struct.unpack_from("<Q", data, magic_pos - 8)[0]
    block_start = magic_pos + 16 - size2 - 8
    assert struct.unpack_from("<Q", data, block_start)[0] == size2, "size mismatch"

    real_cd = struct.unpack_from("<I", data, data.rfind(b"PK\x05\x06") + 16)[0]
    assert real_cd == block_start + 8 + size2, "EOCD cd-offset should point to real CD"
    eocd_off = data.rfind(b"PK\x05\x06")
    # 段 3 = EOCD 但 offset 改回签名块起点（apksig 惯例：摘要用"插入前"的 EOCD）
    eocd = bytearray(data[eocd_off:])
    struct.pack_into("<I", eocd, 16, block_start)
    sections = [data[:block_start], data[real_cd:eocd_off], bytes(eocd)]

    # 遍历 pairs 找 v2
    off = block_start + 8
    found = None
    while off < block_start + 8 + size2 - 24:
        plen = struct.unpack_from("<Q", data, off)[0]
        pid = struct.unpack_from("<I", data, off + 8)[0]
        if pid == V2_BLOCK_ID:
            found = data[off + 12: off + 8 + plen]
        off += 8 + plen
    assert found, "v2 pair not found"

    # value = u32 signers_len + signers_blob
    sb_len = struct.unpack_from("<I", found, 0)[0]
    sb = found[4:4 + sb_len]
    sg_len = struct.unpack_from("<I", sb, 0)[0]
    signer = sb[4:4 + sg_len]
    # signer = u32 sd_len + signedData + u32 sigs_len + sigsSeq + u32 pk_len + publicKey
    sd_len = struct.unpack_from("<I", signer, 0)[0]
    signed_data = signer[4:4 + sd_len]
    rest = signer[4 + sd_len:]
    sigs_len = struct.unpack_from("<I", rest, 0)[0]
    sigs_seq = rest[4:4 + sigs_len]
    pk_len = struct.unpack_from("<I", rest, 4 + sigs_len)[0]
    pubkey = rest[8 + sigs_len: 8 + sigs_len + pk_len]

    # sigsSeq = 单条记录 [recLen][alg][sigLen][sig]
    rec_len, alg, sig_len = struct.unpack_from("<III", sigs_seq, 0)
    sig = sigs_seq[12:12 + sig_len]
    assert alg == ALG_RSA_PKCS1_SHA256, "alg id"
    assert rec_len == 4 + 4 + sig_len, "record length"
    expected_pk = key.public_key().public_bytes(
        serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
    assert pubkey == expected_pk, "public key mismatch"
    key.public_key().verify(sig, signed_data, padding.PKCS1v15(), hashes.SHA256())
    assert cert.public_bytes(serialization.Encoding.DER) in signed_data, "cert not in signed data"

    # 摘要比对：signedData = u32(len) digestsSeq + u32(len) certs + u32(len) attrs
    # digestsSeq = [recLen][alg][dLen][digest]
    dg_len = struct.unpack_from("<I", signed_data, 0)[0]
    digests_seq = signed_data[4:4 + dg_len]
    d_rec, d_alg, d_len = struct.unpack_from("<III", digests_seq, 0)
    stored = digests_seq[12:12 + d_len]
    content_digest = chunked_sha256(sections)
    assert d_alg == ALG_RSA_PKCS1_SHA256 and stored == content_digest, "digest mismatch!"
    print("verify OK: RSA signature valid, content digest matches, public key & cert match")


# ---------------------------------------------------------------- main
def b64p(b): return base64.b64encode(b).decode()[:24] + "..."


def main():
    args = sys.argv[1:]
    key, cert = load_or_create_keys()
    if args and args[0] == "--verify":
        verify_v2(args[1], key, cert)
        return
    src, dst = args[0], args[1]
    tmp = dst + ".v1.tmp"
    v1_sign(src, tmp, key, cert)
    v2_sign_file(tmp, key, cert)
    os.replace(tmp, dst)
    print("signed (v1+v2):", dst, f"({os.path.getsize(dst)} bytes)")
    verify_v2(dst, key, cert)


if __name__ == "__main__":
    main()
