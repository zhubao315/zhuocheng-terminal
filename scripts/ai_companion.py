#!/usr/bin/env python3
"""拙诚日课终端 · AI 伴读

companion.json 为自包含条目库（原文+解读+思考题），按索引推送到 PhoneBox。
内容预生成，不依赖 API key、不联网。支持随机轮播（中枢每 30 秒调用一次）。

用法：
  python ai_companion.py --setup      # 首次：建 companion 页面 + 推送 + 切页
  python ai_companion.py              # 随机推一条
  python ai_companion.py --index 3    # 指定索引（测试）
  python ai_companion.py --list       # 列出全部条目
"""
import json
import random
import re
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
PAGE_ID = "companion"
KEYS = {"passage": "ai-passage", "insight": "ai-insight"}
STATE = BASE / ".companion_state.json"


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


def load_companions():
    return json.loads((DATA_DIR / "companion.json").read_text(encoding="utf-8"))["items"]


def choose_index(n, last=None):
    """随机选一条，尽量不与上一条重复。"""
    if "--index" in sys.argv:
        return int(sys.argv[sys.argv.index("--index") + 1]) % n
    if n <= 1:
        return 0
    pool = [i for i in range(n) if i != last]
    return random.choice(pool)


def group_fragments(text, maxlen=32):
    """按中文标点切开再合并到每行不超过 maxlen 字，保证列表单行不省略。"""
    parts = [s.strip() for s in re.split(r"[。；，、：]", text) if s.strip()]
    groups, buf = [], ""
    for p in parts:
        cand = buf + ("，" if buf else "") + p
        if len(cand) <= maxlen:
            buf = cand
        else:
            if buf:
                groups.append(buf)
            buf = p
    if buf:
        groups.append(buf)
    return groups


def setup_page():
    cfg = request("GET", "/api/settings")
    pages = cfg.get("pages", [])
    page = next((p for p in pages if p.get("id") == PAGE_ID), None)
    if page is None:
        page = {"id": PAGE_ID, "title": "AI 伴读", "icon": "🧭", "enabled": True, "widgets": []}
        pages.append(page)
        print(f"✓ 新建页面 {PAGE_ID}")

    # push 组件 .pv 写死 nowrap+省略号，长原文会截断；改 HTML 组件自动换行
    passage_html = """<style>
  .wrap{height:100%;box-sizing:border-box;padding:1.2vh 1.8vw;display:flex;flex-direction:column;justify-content:center;gap:1vh}
  .t{font-size:clamp(11px,2vh,20px);color:#8a94a3;letter-spacing:.12em;text-transform:uppercase}
  .v{font-size:min(22vh,8vw);line-height:1.4;color:#eef2f6;overflow-wrap:break-word;word-break:break-word;transform:translateZ(0)}
  .s{font-size:clamp(14px,3.2vh,30px);color:#8a94a3}
</style>
<div class="wrap"><div class="t">QUOTE · 今日伴读 · 原文</div><div class="v" id="pv">等待推送…</div><div class="s" id="ps"></div></div>
<script>
  function put(id,txt){var e=document.getElementById(id);if(e.textContent===txt)return;var n=e.cloneNode(false);n.textContent=txt;e.parentNode.replaceChild(n,e);}
  function show(){var p=(window.phonebox&&phonebox.data&&phonebox.data.push)||{};var d=p['ai-passage'];if(d&&d.data){put('pv',d.data.value||'—');put('ps',d.data.sub||'');}}
  phonebox.on('push',show);show();
</script>"""
    widgets = [
        {"id": "ai-passage-w", "type": "html", "x": 0, "y": 0, "w": 12, "h": 2,
         "options": {"html": passage_html, "transparent": False}},
        {"id": "ai-insight-w", "type": "push", "x": 0, "y": 2, "w": 12, "h": 4,
         "options": {"key": KEYS["insight"], "title": "AI 解读 + 今日一问", "style": "list"}},
    ]
    existing = {w.get("id"): w for w in page.get("widgets", [])}
    existing.pop("ai-question-w", None)  # 问题已并入解读列表，移除旧组件
    for w in widgets:
        existing[w["id"]] = w
    page["widgets"] = list(existing.values())

    request("PUT", "/api/settings", cfg)
    print("✓ 页面配置已写入")


def push_companion(idx, items=None):
    """推一条伴读（供中枢直接调用）。返回 idx。"""
    items = items if items is not None else load_companions()
    c = items[idx]
    request("POST", "/api/push/" + KEYS["passage"], {
        "value": c["passage"], "sub": c["source"], "title": "今日伴读 · 原文", "icon": "quote",
    })
    # list 样式的单行仍是 nowrap+省略号，所以拆成短句；
    # 问题也并入同一个列表，避免底部组件被屏幕边缘裁掉。
    parts = group_fragments(c["insight"])
    request("POST", "/api/push/" + KEYS["insight"], {
        "items": parts + [
            f"#{c['tag']} · 关联日课：{c['practice']}",
            f"❓ 今日一问：{c['question']}",
            "✍️ 答完再勾一条日课",
        ],
        "title": "AI 解读 + 今日一问", "icon": "spark",
    })
    return idx


def main():
    items = load_companions()
    if "--list" in sys.argv:
        for i, c in enumerate(items):
            print(f"{i:2}. [{c['tag']}] {c['passage'][:24]}… — {c['source']}")
        return

    if "--setup" in sys.argv:
        setup_page()

    st = {}
    if STATE.exists():
        try:
            st = json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            st = {}
    idx = choose_index(len(items), st.get("index"))
    push_companion(idx, items)
    STATE.write_text(json.dumps({"index": idx}, ensure_ascii=False), encoding="utf-8")
    print(f"✓ 伴读 [{idx}] 已推送：{items[idx]['source']} · {items[idx]['tag']}")

    if "--setup" in sys.argv:
        time.sleep(2)  # 等手机重载完成，否则 goto 会被吞
        request("POST", "/api/goto/" + PAGE_ID + "?countdown=0")
        print("✓ 已切到 AI 伴读页")


if __name__ == "__main__":
    main()
