#!/usr/bin/env python3
"""把金句推到 PhoneBox 面板。

用法:
  python push_quote.py          # 按顺序推下一条（轮播）
  python push_quote.py 0        # 推指定索引
  python push_quote.py --list   # 列出全部金句
  python push_quote.py --notify # 推送并弹通知唤醒屏幕

数据源: quotes.json  ->  items[]
推送端点: POST http://127.0.0.1:8765/api/push/<key>
"""
import json
import sys
import urllib.request
from pathlib import Path

BASE = Path(__file__).parent
import os
DATA_DIR = Path(os.environ.get(
    "PHONEBOX_DATA_DIR",
    Path(__file__).resolve().parent.parent / "data"))

import os
DATA_DIR = Path(os.environ.get(
    "PHONEBOX_DATA_DIR",
    Path(__file__).resolve().parent.parent / "data"))

import os
DATA_DIR = Path(os.environ.get(
    "PHONEBOX_DATA_DIR",
    Path(__file__).resolve().parent.parent / "data"))

import os
DATA_DIR = Path(os.environ.get(
    "PHONEBOX_DATA_DIR",
    Path(__file__).resolve().parent.parent / "data"))

DATA = json.loads((DATA_DIR / "quotes.json").read_text(encoding="utf-8"))
KEY = DATA["meta"]["push_key"]
ITEMS = DATA["items"]
STATE = BASE / ".quote_index"

API = os.environ.get("PHONEBOX_API", "http://127.0.0.1:8765")


def post(path, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        API + path,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=5) as r:
        return r.read().decode("utf-8")


def main():
    args = sys.argv[1:]

    if "--list" in args:
        for i, it in enumerate(ITEMS):
            print(f"{i:2}. {it['text']}  —— {it['source']}")
        return

    notify = "--notify" in args
    nums = [a for a in args if a.isdigit()]
    if nums:
        idx = int(nums[0]) % len(ITEMS)
    else:
        idx = int(STATE.read_text().strip()) if STATE.exists() else 0
        idx = idx % len(ITEMS)

    it = ITEMS[idx]
    payload = {
        "value": it["text"],
        "sub": it["source"],
        "title": "每日金句",
        "icon": "quote",
    }
    print(post(f"/api/push/{KEY}", payload))
    if notify:
        print(post("/api/notify", {
            "title": "每日金句",
            "text": it["text"][:60],
            "level": "ok",
            "wake": True,
            "seconds": 5,
        }))
    STATE.write_text(str(idx + 1))
    print(f"[{idx}] {it['text']}  —— {it['source']}")


if __name__ == "__main__":
    main()
