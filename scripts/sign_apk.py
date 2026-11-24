#!/usr/bin/env python3
"""给修改过的 PhoneBox APK 生成 v1(JAR) 签名，产出可直接 adb install 的 APK。

Android 9 接受 v1-only 签名。密钥/证书现场生成（自签，20 年有效期）。
用法：python sign_apk.py <in.apk> <out.apk>
"""
import base64
import datetime
import hashlib
import re
import sys
import zipfile

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives.serialization import pkcs7


def b64(data: bytes) -> str:
    return base64.b64encode(hashlib.sha256(data).digest()).decode()


def manifest_str(name: str, data: bytes) -> bytes:
    # JAR manifest 每行不超过 72 字节，长路径用 "\r\n " 续行
    out = bytearray()
    line = "Name: " + name
    while len(line.encode()) > 72:
        cut = 72
        while cut > 1 and (line[cut] if cut < len(line) else " "):
            cut -= 1
        # 简化：直接按字节切到 72 以内
        raw = line.encode()
        out += raw[:71] + b"\r\n "
        line = raw[71:].decode(errors="replace")
    out += line.encode() + b"\r\n"
    out += b"SHA-256-Digest: " + b64(data).encode() + b"\r\n\r\n"
    return bytes(out)


def main(src, dst):
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([
        x509.NameAttribute(NameOID.COMMON_NAME, u"WorkBuddy Local Signer"),
        x509.NameAttribute(NameOID.ORGANIZATION_NAME, u"Local"),
    ])
    now = datetime.datetime.now(datetime.timezone.utc)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name).issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=7300))
        .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM)
    print("key/certificate generated")

    zin = zipfile.ZipFile(src)
    entries = [i for i in zin.infolist() if not re.match(r"^META-INF/.*\.(SF|RSA|DSA|EC)$", i.filename)]

    # 1) MANIFEST.MF
    mf = bytearray(b"Manifest-Version: 1.0\r\nCreated-By: 1.0 (WorkBuddy)\r\n\r\n")
    for item in entries:
        if item.filename == "META-INF/MANIFEST.MF":
            continue
        mf += manifest_str(item.filename, zin.read(item.filename))
    mf = bytes(mf)

    # 2) CERT.SF — 主属性 + 每个条目的 digest（per-entry，Android fallback 校验需要）
    sf = bytearray(
        b"Signature-Version: 1.0\r\nCreated-By: 1.0 (WorkBuddy)\r\n"
        + b"X-Android-Created-By: WorkBuddy signer\r\n"
        + b"SHA-256-Digest-Manifest: " + b64(mf).encode() + b"\r\n\r\n"
    )
    for item in entries:
        if item.filename == "META-INF/MANIFEST.MF":
            continue
        sf += manifest_str(item.filename, zin.read(item.filename))
    sf = bytes(sf)

    # 3) CERT.RSA — PKCS#7 detached 签名 CERT.SF
    builder = (
        pkcs7.PKCS7SignatureBuilder()
        .set_data(sf)
        .add_signer(cert, key, hashes.SHA256())
        .sign(serialization.Encoding.DER, [pkcs7.PKCS7Options.DetachedSignature, pkcs7.PKCS7Options.Binary, pkcs7.PKCS7Options.NoCapabilities])
    )

    zout = zipfile.ZipFile(dst, "w", zipfile.ZIP_DEFLATED)
    for item in entries:
        if item.filename == "META-INF/MANIFEST.MF":
            zout.writestr("META-INF/MANIFEST.MF", mf)
            continue
        data = zin.read(item.filename)
        if item.filename == "assets/www/index.html":
            pass  # 已在 src 中修改过
        zout.writestr(item, data)
    zout.writestr("META-INF/CERT.SF", sf)
    zout.writestr("META-INF/CERT.RSA", builder)
    zout.close()
    zin.close()
    print("signed:", dst, f"({len(builder)} bytes PKCS7)")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2])
