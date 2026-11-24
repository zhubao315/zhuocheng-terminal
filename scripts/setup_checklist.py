#!/usr/bin/env python3
"""把 rike_items.json 的日课条目推送为 PhoneBox 两列触屏勾选清单。

零依赖，走 PhoneBox 本地 API，无需重启 Agent：
  GET  /api/settings        读取当前配置
  PUT  /api/settings        写回加了 checklist 组件的配置
  POST /api/refresh?reload=true 让手机重载面板
  POST /api/goto/checkin?countdown=0 切到日课页

用法：
  python setup_checklist.py            # 推送并切页
  python setup_checklist.py --dry-run  # 只打印将写入的组件，不改动
"""
import datetime
import json
import sys
import time
import urllib.request
from pathlib import Path

BASE = Path(__file__).parent
import os
DATA_DIR = Path(os.environ.get(
    "PHONEBOX_DATA_DIR",
    Path(__file__).resolve().parent.parent / "data"))

API = os.environ.get("PHONEBOX_API", "http://127.0.0.1:8765")
PAGE_ID = "checkin"
WIDGET_IDS = ("rike-checklist-a", "rike-checklist-b")


def request(method, path, payload=None):
    data = None
    headers = {}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(API + path, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as r:
        raw = r.read().decode("utf-8", "replace")
        return json.loads(raw) if raw.strip().startswith(("{", "[")) else raw


def checklist_widget(items, title, x, idx):
    return {
        "id": WIDGET_IDS[idx],
        "type": "checklist",
        "x": x,
        "y": 0,
        "w": 6,
        "h": 6,
        "appearance": {"fontScale": 125},
        "options": {"title": title, "items": items, "daily": True},
    }


def main():
    data = json.loads((DATA_DIR / "rike_items.json").read_text(encoding="utf-8"))
    items = data["items"]
    titles = data["meta"].get("column_titles", ["日课 · 上（1-6）", "日课 · 下（7-12）"])
    half = (len(items) + 1) // 2

    cfg = request("GET", "/api/settings")
    pages = cfg.get("pages", [])
    page = next((p for p in pages if p.get("id") == PAGE_ID), None)
    if page is None:
        raise SystemExit(f"找不到页面 {PAGE_ID}，请先运行 setup_overview.py")

    widgets = [
        checklist_widget(items[:half], titles[0], 0, 0),
        checklist_widget(items[half:], titles[1], 6, 1),
    ]
    if "--dry-run" in sys.argv:
        print(json.dumps(widgets, ensure_ascii=False, indent=2))
        return

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    (BASE / f"config_before_checklist_{stamp}.json").write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    old = set(WIDGET_IDS) | {"rike-checklist"}
    kept = [w for w in page.get("widgets", []) if w.get("id") not in old]
    page["widgets"] = kept + widgets

    request("PUT", "/api/settings", cfg)
    print("✓ 配置已写入（两列日课清单，字号 125%）")

    request("POST", "/api/refresh?reload=true")
    print("✓ 面板已重载")
    time.sleep(2)
    try:
        request("POST", "/api/goto/" + PAGE_ID + "?countdown=0")
        print("✓ 已切到日课页")
    except Exception as e:
        print(f"切页跳过（手机可能离线）：{e}")

    print(f"✓ 清单 {len(items)} 条已分两列上线：{titles[0]} / {titles[1]}")


if __name__ == "__main__":
    main()
