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

    # 伴读页 v2：单屏阅读器 —— 原文/解读/一问同屏分层，中枢每 10 分钟推一组
    # （5 条），组内自由翻阅、可暂停；不做自动轮换打断阅读
    READER_HTML = """<style>
  .wrap{height:100%;box-sizing:border-box;padding:1vh 1.8vw .8vh;display:flex;flex-direction:column;gap:.7vh}
  .t{font-size:clamp(11px,2vh,20px);color:#8a94a3;letter-spacing:.12em;display:flex;justify-content:space-between;align-items:center}
  .badge{font-size:clamp(10px,1.7vh,17px);color:#2dd4bf;letter-spacing:0;white-space:nowrap}
  .pass{min-height:0;flex:0 1 auto;font-size:min(7.2vh,4.2vw);line-height:1.4;color:#eef2f6;overflow-wrap:break-word;word-break:break-word;transform:translateZ(0)}
  .src{font-size:clamp(12px,2.2vh,21px);color:#8a94a3;overflow-wrap:break-word;word-break:break-word}
  .div{height:1px;background:rgba(45,212,191,.25);flex:none}
  .ins{flex:1;min-height:0;overflow:hidden;font-size:clamp(13px,2.5vh,23px);line-height:1.5;color:#b8c2cf;overflow-wrap:break-word;word-break:break-word;transform:translateZ(0)}
  .q{flex:none;font-size:clamp(13px,2.5vh,23px);line-height:1.4;color:#f59e0b;overflow-wrap:break-word;word-break:break-word}
  .ctr{display:flex;gap:1vw;padding-top:.4vh;flex:none}
  .btn{flex:1;height:clamp(32px,5vh,48px);border-radius:10px;border:1px solid rgba(45,212,191,.4);background:rgba(45,212,191,.10);color:#2dd4bf;font-size:clamp(13px,2.2vh,21px);display:flex;align-items:center;justify-content:center;user-select:none;-webkit-user-select:none;-webkit-tap-highlight-color:transparent}
  .btn:active{background:rgba(45,212,191,.28)}
  .btn.on{background:rgba(245,158,11,.18);border-color:rgba(245,158,11,.5);color:#f59e0b}
</style>
<div class="wrap">
  <div class="t"><span>伴读 · 原文</span><span class="badge" id="cb">—</span></div>
  <div class="pass" id="cv">等待推送…</div>
  <div class="src" id="cs"></div>
  <div class="div"></div>
  <div class="ins" id="ci">解读加载中…</div>
  <div class="q" id="cq"></div>
  <div class="ctr">
    <div class="btn" id="bPrev">‹ 上一条</div>
    <div class="btn" id="bPause">⏸ 暂停轮换</div>
    <div class="btn" id="bNext">下一条 ›</div>
  </div>
</div>
<script>
  var batch=null,bi=0,paused=false,bn=-1;
  function put(id,txt){var e=document.getElementById(id);if(e.textContent===txt)return;var n=e.cloneNode(false);n.textContent=txt;e.parentNode.replaceChild(n,e);}
  function render(){
    if(!batch||!batch.items||!batch.items.length)return;
    var L=batch.items.length;
    bi=((bi%L)+L)%L;
    var it=batch.items[bi];
    put('cv',it.passage||'—');
    put('cs',it.source||'');
    put('ci',it.insight||'');
    put('cq',it.question?('❓ 今日一问：'+it.question+'　✍️ 关联日课：'+it.practice):'');
    put('cb','组内 '+(bi+1)+'/'+L+' · #'+(it.tag||'')+(paused?' · 已暂停':''));
  }
  function grab(){
    var p=(window.phonebox&&phonebox.data&&phonebox.data.push)||{};
    var d=p['companion-batch'];
    if(d&&d.data&&d.data.batch_no!==bn){bn=d.data.batch_no;batch=d.data;bi=0;
      if(!paused)render();else put('cb','新组已到 · 已暂停');return;}
    if(!batch){var s=p['ai-passage'];if(s&&s.data){put('cv',s.data.value||'—');put('cs',s.data.sub||'');put('cb','单条模式');}}
  }
  document.getElementById('bPrev').addEventListener('click',function(){if(batch){bi--;render();}});
  document.getElementById('bNext').addEventListener('click',function(){if(batch){bi++;render();}});
  document.getElementById('bPause').addEventListener('click',function(){
    paused=!paused;
    var b=document.getElementById('bPause');
    b.textContent=paused?'▶ 继续轮换':'⏸ 暂停轮换';
    b.className=paused?'btn on':'btn';
    render();
  });
  phonebox.on('push',grab);grab();
</script>"""
    widgets = [
        {"id": "ai-reader-h", "type": "html", "x": 0, "y": 0, "w": 12, "h": 6,
         "options": {"html": READER_HTML, "transparent": False}},
    ]
    # 清理旧版组件（含历次部署遗留的 -h-2 / -h-3 … 后缀）
    for legacy in ("ai-passage", "ai-insight", "ai-question", "ai-reader"):
        page["widgets"] = [w for w in page.get("widgets", [])
                           if not str(w.get("id", "")).startswith(legacy)]
    for w in widgets:
        page["widgets"].append(w)

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
