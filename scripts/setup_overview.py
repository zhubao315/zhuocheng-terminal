#!/usr/bin/env python3
"""拙诚日课终端 · 总览页 + 全局字号 + 日课两列，一键部署。

零依赖，走 PhoneBox 本地 API，无需重启 Agent：
  GET  /api/settings          读配置
  PUT  /api/settings          写回
  POST /api/refresh?reload=true  手机重载
  POST /api/goto/overview?countdown=0  切到总览页

用法：
  python setup_overview.py            # 部署并切页
  python setup_overview.py --dry-run  # 只预览，不改动
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
TARGET_PAGE = "overview"

OVERVIEW_HTML = """<style>
  .wrap{height:100%;box-sizing:border-box;padding:1.4vh 2vw;display:flex;flex-direction:column;gap:1.2vh}
  .head{display:flex;align-items:baseline;gap:1.6vw}
  .head b{font-size:clamp(20px,4.4vh,46px);color:#2dd4bf;letter-spacing:.08em;font-weight:700}
  .head span{font-size:clamp(11px,1.9vh,20px);color:#8a94a3}
  .grid{flex:1;min-height:0;display:grid;grid-template-columns:repeat(3,1fr);grid-template-rows:repeat(2,1fr);gap:1.2vh 1.2vw}
  .tile{border:1px solid rgba(45,212,191,.32);border-radius:14px;background:rgba(45,212,191,.08);color:#eef2f6;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:.5vh;cursor:pointer;transition:transform .1s,background .1s}
  .tile:active{transform:scale(.96);background:rgba(45,212,191,.22)}
  .tile .ic{font-size:clamp(26px,6vh,60px);line-height:1}
  .tile .nm{font-size:clamp(17px,3.2vh,34px);font-weight:700}
  .tile .ds{font-size:clamp(10px,1.7vh,18px);color:#8a94a3}
</style>
<div class="wrap">
  <div class="head"><b>拙诚日课终端</b><span>· 五阶段 · 触屏切换</span></div>
  <div class="grid">
    <button class="tile" data-go="rike"><span class="ic">💬</span><span class="nm">每日金句</span><span class="ds">大字金句 · 品读语境</span></button>
    <button class="tile" data-go="checkin"><span class="ic">✅</span><span class="nm">日课打卡</span><span class="ds">十二条目 · 微习惯 · 提醒</span></button>
    <button class="tile" data-go="hub"><span class="ic">⏱️</span><span class="nm">定时中枢</span><span class="ds">心跳 · 日课提醒 · 轮播</span></button>
    <button class="tile" data-go="companion"><span class="ic">📖</span><span class="nm">AI 伴读</span><span class="ds">解读 · 思考题</span></button>
    <button class="tile" data-go="ride"><span class="ic">🚴</span><span class="nm">骑行模式</span><span class="ds">GPS · 加速度计</span></button>
    <button class="tile" data-go="home"><span class="ic">🏠</span><span class="nm">系统主页</span><span class="ds">时钟 · 媒体 · 状态</span></button>
  </div>
</div>
<script>
  document.querySelectorAll('[data-go]').forEach(function(b){
    b.addEventListener('click',function(){ phonebox.goto(b.getAttribute('data-go')); });
  });
</script>"""

HUB_HTML = """<style>
  .wrap{height:100%;box-sizing:border-box;padding:1.4vh 2vw;display:flex;flex-direction:column;gap:1vh}
  .head b{font-size:clamp(20px,4.2vh,44px);color:#2dd4bf;letter-spacing:.08em}
  .head span{font-size:clamp(11px,1.9vh,20px);color:#8a94a3;margin-left:1vw}
  .rows{flex:1;min-height:0;display:flex;flex-direction:column;gap:.8vh}
  .row{background:rgba(255,255,255,.05);border-left:4px solid #2dd4bf;border-radius:10px;padding:.7vh 1.5vw;display:flex;flex-direction:column;justify-content:center;min-height:0}
  .row .k{font-size:clamp(11px,1.7vh,18px);color:#8a94a3}
  .row .v{font-size:clamp(16px,2.8vh,30px);color:#eef2f6;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;transform:translateZ(0)}
  .row.hl{border-left-color:#f59e0b}
  .foot{font-size:clamp(10px,1.6vh,17px);color:#8a94a3}
</style>
<div class="wrap">
  <div class="head"><b>定时中枢</b><span>电脑端 Python · 10 秒心跳</span></div>
  <div class="rows">
    <div class="row hl"><span class="k" id="kr">日课提醒</span><span class="v" id="r">等待推送…</span></div>
    <div class="row hl"><span class="k" id="km">今日微习惯</span><span class="v" id="h">等待推送…</span></div>
    <div class="row"><span class="k" id="kq">今日金句</span><span class="v" id="q">等待推送…</span></div>
    <div class="row"><span class="k" id="kb">手机电量 / 温度</span><span class="v" id="b">等待推送…</span></div>
    <div class="row"><span class="k" id="ks">环境感知</span><span class="v" id="s">等待推送…</span></div>
    <div class="row"><span class="k" id="ki">中枢心跳</span><span class="v" id="i">等待推送…</span></div>
  </div>
  <div class="foot">金句 10s · 伴读 30s · 日课提醒 15min · 微习惯 60min · 硬件 90s · 离线照常轮播</div>
</div>
<script>
  function item(k){var p=(window.phonebox&&phonebox.data&&phonebox.data.push)||{};return p[k]&&p[k].data?p[k].data:null;}
  function show(){
    [['rike-reminder','r','kr','日课提醒'],['micro-habit','h','km','今日微习惯'],['daily-quote','q','kq','今日金句'],['phone-batt','b','kb','手机电量 / 温度'],['phone-sensor','s','ks','环境感知'],['hub-info','i','ki','中枢心跳']].forEach(function(t){
      var d=item(t[0]);
      document.getElementById(t[1]).textContent=d?(d.value||'—'):'等待推送…';
      document.getElementById(t[2]).textContent=(d&&d.sub)?d.sub:t[3];
    });
  }
  phonebox.on('push',show);show();
</script>"""


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


def upsert_page(pages, page_id, title, icon, widgets, first=False):
    page = next((p for p in pages if p.get("id") == page_id), None)
    if page is None:
        page = {"id": page_id, "title": title, "icon": icon, "enabled": True, "widgets": []}
        (pages.insert(0, page) if first else pages.append(page))
        print(f"✓ 新建页面 {page_id}" + ("（首页）" if first else ""))
    else:
        page["title"] = title
        page["icon"] = icon
        page["enabled"] = True
    existing = {w.get("id"): w for w in page.get("widgets", [])}
    for w in widgets:
        existing[w["id"]] = w
    page["widgets"] = list(existing.values())
    return page


def main():
    cfg = request("GET", "/api/settings")
    pages = cfg.get("pages", [])
    items = json.loads((DATA_DIR / "rike_items.json").read_text(encoding="utf-8"))["items"]

    # 备份，便于回滚（带时间戳，不覆盖上一版）
    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    (BASE / f"config_before_overview_{stamp}.json").write_text(
        json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    # 1) 全局字号：每档 5%，120% = 比原来大四档；用户要求"字号都大一些"
    display = cfg.setdefault("display", {})
    appearance = display.setdefault("appearance", {})
    appearance["fontScale"] = 120

    # 2) 总览页（置顶为首页），五个阶段一键切换
    upsert_page(pages, "overview", "总览", "🧭", [{
        "id": "overview-menu", "type": "html", "x": 0, "y": 0, "w": 12, "h": 6,
        "appearance": {"fontScale": 110},
        "options": {"html": OVERVIEW_HTML, "transparent": False},
    }], first=True)

    # 3) 定时中枢独立页面（此前中枢只有后台脚本，没有可视页）
    upsert_page(pages, "hub", "定时中枢", "⏱️", [{
        "id": "hub-status", "type": "html", "x": 0, "y": 0, "w": 12, "h": 6,
        "appearance": {"fontScale": 110},
        "options": {"html": HUB_HTML, "transparent": False},
    }])

    # 4) 金句页：push 组件的 .pv 样式写死 nowrap+省略号，长文必截断；
    #    改用 HTML 组件自动换行，字号用容器单位保持"大字"观感
    QUOTE_HTML = """<style>
  .wrap{height:100%;box-sizing:border-box;padding:1.2vh 1.8vw;display:flex;flex-direction:column;justify-content:center;gap:1.2vh}
  .t{font-size:clamp(11px,2vh,20px);color:#8a94a3;letter-spacing:.12em;text-transform:uppercase}
  .v{font-size:min(13.5vh,7.6vw);line-height:1.4;color:#eef2f6;overflow-wrap:break-word;word-break:break-word;font-weight:400;transform:translateZ(0)}
  .s{font-size:clamp(14px,3.2vh,30px);color:#8a94a3}
</style>
<div class="wrap"><div class="t">QUOTE · 每日金句</div><div class="v" id="qv">等待推送…</div><div class="s" id="qs"></div></div>
<script>
  function put(id,txt){var e=document.getElementById(id);if(e.textContent===txt)return;var n=e.cloneNode(false);n.textContent=txt;e.parentNode.replaceChild(n,e);}
  function show(){var p=(window.phonebox&&phonebox.data&&phonebox.data.push)||{};var d=p['daily-quote'];if(d&&d.data){put('qv',d.data.value||'—');put('qs',d.data.sub||'');}}
  phonebox.on('push',show);show();
</script>"""
    rike = next((p for p in pages if p.get("id") == "rike"), None)
    if rike:
        # 去重：清掉 quote-main 和历次部署遗留的 quote-main-h / -h-2 / -h-3 …
        rike["widgets"] = [w for w in rike["widgets"]
                           if not str(w.get("id", "")).startswith("quote-main")]

    # 金句页下半屏：品读语境（主题·出处 + 时辰宜事），替代原先的电量/亮度组件
    QUOTE_FOOT_HTML = """<style>
  .wrap{height:100%;box-sizing:border-box;padding:.6vh 1.8vw 1vh;display:flex;gap:1.2vw}
  .card{flex:1;min-width:0;background:rgba(45,212,191,.07);border:1px solid rgba(45,212,191,.25);border-radius:12px;padding:.8vh 1.4vw;display:flex;flex-direction:column;justify-content:center;gap:.4vh}
  .k{font-size:clamp(10px,1.8vh,18px);color:#2dd4bf;letter-spacing:.1em}
  .v{font-size:clamp(14px,2.7vh,27px);color:#eef2f6;overflow-wrap:break-word;word-break:break-word;transform:translateZ(0)}
  .s{font-size:clamp(11px,1.9vh,19px);color:#8a94a3;overflow-wrap:break-word;word-break:break-word}
</style>
<div class="wrap">
  <div class="card"><span class="k">🏷️ 主题 · 出处</span><span class="v" id="fm">等待推送…</span><span class="s" id="fs"></span></div>
  <div class="card"><span class="k">🕰️ 时辰宜事</span><span class="v" id="hv">等待推送…</span><span class="s" id="hs"></span></div>
</div>
<script>
  function put(id,txt){var e=document.getElementById(id);if(e.textContent===txt)return;var n=e.cloneNode(false);n.textContent=txt;e.parentNode.replaceChild(n,e);}
  function show(){var p=(window.phonebox&&phonebox.data&&phonebox.data.push)||{};
    var m=p['quote-meta'];if(m&&m.data){put('fm',m.data.value||'—');put('fs',m.data.sub||'');}
    var h=p['quote-hour'];if(h&&h.data){put('hv',h.data.value||'—');put('hs',h.data.sub||'');}}
  phonebox.on('push',show);show();
</script>"""
    if rike:
        rike["widgets"] = [w for w in rike["widgets"] if w.get("id") not in {"phone-batt", "phone-sensor"}]
        rike["widgets"].append({
            "id": "quote-main-h", "type": "html", "x": 0, "y": 0, "w": 12, "h": 4,
            "options": {"html": QUOTE_HTML, "transparent": False},
        })
        rike["widgets"].append({
            "id": "quote-foot", "type": "html", "x": 0, "y": 4, "w": 12, "h": 2,
            "options": {"html": QUOTE_FOOT_HTML, "transparent": False},
        })
    else:
        print("⚠ 找不到 rike 页，金句组件未调整")

    # 5) 日课两列 + 顶部微习惯条：保留原生 checklist 的勾选/震动/每日清零
    MICRO_BAR_HTML = """<style>
  .bar{height:100%;box-sizing:border-box;display:flex;align-items:center;gap:1.2vw;padding:0 1.5vw;background:rgba(245,158,11,.10);border:1px solid rgba(245,158,11,.35);border-radius:10px;overflow:hidden}
  .k{font-size:clamp(12px,2.2vh,22px);color:#f59e0b;font-weight:700;white-space:nowrap}
  .v{font-size:clamp(13px,2.4vh,24px);color:#eef2f6;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;transform:translateZ(0)}
  .s{font-size:clamp(10px,1.8vh,18px);color:#8a94a3;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
</style>
<div class="bar"><span class="k">🎯 微习惯</span><span class="v" id="mh">等待推送…</span><span class="s" id="ms"></span></div>
<script>
  function show(){var p=(window.phonebox&&phonebox.data&&phonebox.data.push)||{};var d=p['micro-habit'];if(d&&d.data){document.getElementById('mh').textContent=d.data.value||'—';document.getElementById('ms').textContent=d.data.sub?'· '+d.data.sub:'';}}
  phonebox.on('push',show);show();
</script>"""
    checkin = next((p for p in pages if p.get("id") == "checkin"), None)
    if checkin:
        old_ids = {"rike-checklist", "rike-checklist-a", "rike-checklist-b", "micro-habit-w", "micro-habit-bar"}
        widgets = [w for w in checkin["widgets"] if w.get("id") not in old_ids]
        widgets.append({
            "id": "micro-habit-bar", "type": "html", "x": 0, "y": 0, "w": 12, "h": 1,
            "options": {"html": MICRO_BAR_HTML, "transparent": False},
        })
        half = (len(items) + 1) // 2
        for idx, (part, title, x) in enumerate([
            (items[:half], "日课 · 上", 0),
            (items[half:], "日课 · 下", 6),
        ]):
            widgets.append({
                "id": f"rike-checklist-{'ab'[idx]}", "type": "checklist",
                "x": x, "y": 1, "w": 6, "h": 5,
                "appearance": {"fontScale": 125},
                "options": {"title": title, "items": part, "daily": True},
            })
        checkin["widgets"] = widgets
    else:
        print("⚠ 找不到 checkin 页，日课两列未调整")

    if "--dry-run" in sys.argv:
        print(json.dumps({
            "display.appearance": appearance,
            "pages": [(p.get("id"), [(w.get("id"), w.get("type"), w.get("x"), w.get("w")) for w in p.get("widgets", [])]) for p in pages],
        }, ensure_ascii=False, indent=2))
        return

    request("PUT", "/api/settings", cfg)
    print("✓ 配置已写入（总览页 / 定时中枢页 / 字号 / 日课两列 + 微习惯条）")

    request("POST", "/api/refresh?reload=true")
    print("✓ 面板已重载")
    time.sleep(2)
    try:
        request("POST", "/api/goto/" + TARGET_PAGE + "?countdown=0")
        print("✓ 已切到总览页")
    except Exception as e:
        print(f"切页跳过（手机可能离线）：{e}")


if __name__ == "__main__":
    main()
