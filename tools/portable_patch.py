# -*- coding: utf-8 -*-
"""一次性补丁：把 scripts/ 里的脚本改成可移植版（仓库发布用）。
- adb 路径 / API 地址 / WiFi 地址 / 数据目录 全部支持环境变量覆盖
- 运行仓库版时默认把数据目录指向上级 data/
"""
import re
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / "scripts"
DATA_NAMES = {"quotes.json", "companion.json", "microhabits.json", "rike_items.json"}

HDR = '''import os
DATA_DIR = Path(os.environ.get(
    "PHONEBOX_DATA_DIR",
    Path(__file__).resolve().parent.parent / "data"))
'''


def patch(path: Path):
    src = path.read_text(encoding="utf-8")
    orig = src

    # 1) BASE 行后注入 DATA_DIR
    src = src.replace(
        'BASE = Path(__file__).parent',
        'BASE = Path(__file__).parent\n' + HDR, 1)

    # 2) API 地址 → 环境变量
    src = src.replace(
        'API = "http://127.0.0.1:8765"',
        'API = os.environ.get("PHONEBOX_API", "http://127.0.0.1:8765")')

    # 3) adb / WiFi → 环境变量
    src = src.replace(
        'ADB = BASE.parent / "flash-hermes" / "platform-tools" / "adb.exe"',
        'ADB = os.environ.get("PHONEBOX_ADB", "adb")')
    src = src.replace(
        'WIFI_ADDR = "192.168.1.66:5555"',
        'WIFI_ADDR = os.environ.get("PHONEBOX_WIFI_ADB", "192.168.1.66:5555")')

    # 3.5) daily_hub v2 CFG：仓库默认 adb 在 PATH 中、数据目录指向上级 data/
    src = src.replace(
        'str(BASE.parent / "flash-hermes" / "platform-tools" / "adb.exe")',
        '"adb"')
    src = src.replace(
        'Path(_env("PHONEBOX_DATA_DIR", str(BASE)))',
        'Path(_env("PHONEBOX_DATA_DIR", str(BASE.parent / "data")))')

    # 3.6) manage.py：仓库数据目录指向上级 data/
    src = src.replace(
        'Path(os.environ.get("PHONEBOX_DATA_DIR", SCRIPTS))',
        'Path(os.environ.get("PHONEBOX_DATA_DIR", SCRIPTS.parent / "data"))')

    # 4) 数据文件读取 → DATA_DIR
    for name in DATA_NAMES:
        src = src.replace(f'(BASE / "{name}")', f'(DATA_DIR / "{name}")')

    if src != orig:
        path.write_text(src, encoding="utf-8")
        print(f"patched {path.name}")
    else:
        print(f"no-op    {path.name}")


for f in sorted(SCRIPTS.glob("*.py")):
    patch(f)
