#!/usr/bin/env python3
"""拙诚日课 · 总览页 + 全局字号 + 日课两列，一键部署。

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
  <div class="head"><b>拙诚日课</b><span>· 五阶段 · 触屏切换</span></div>
  <div class="grid">
    <button class="tile" data-go="rike"><span class="ic">💬</span><span class="nm">每日金句</span><span class="ds">品读模式 · 暂停/上下句</span></button>
    <button class="tile" data-go="checkin"><span class="ic">✅</span><span class="nm">日课打卡</span><span class="ds">十二条目 · 两列勾选</span></button>
    <button class="tile" data-go="hub"><span class="ic">⏱️</span><span class="nm">定时中枢</span><span class="ds">独立调度 · 断线退避</span></button>
    <button class="tile" data-go="companion"><span class="ic">📖</span><span class="nm">AI 伴读</span><span class="ds">完整阅读 · 手动翻页</span></button>
    <button class="tile" data-go="ride"><span class="ic">🧘</span><span class="nm">静坐三省</span><span class="ds">呼吸引导 · 静坐计时</span></button>
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
  <div class="head"><b>定时中枢</b><span>电脑端 Python · 独立任务调度</span></div>
  <div class="rows">
    <div class="row hl"><span class="k" id="kr">日课提醒</span><span class="v" id="r">等待推送…</span></div>
    <div class="row hl"><span class="k" id="km">今日微习惯</span><span class="v" id="h">等待推送…</span></div>
    <div class="row"><span class="k" id="kq">今日金句</span><span class="v" id="q">等待推送…</span></div>
    <div class="row"><span class="k" id="kb">手机电量 / 温度</span><span class="v" id="b">等待推送…</span></div>
    <div class="row"><span class="k" id="ks">环境感知</span><span class="v" id="s">等待推送…</span></div>
    <div class="row"><span class="k" id="ki">中枢心跳</span><span class="v" id="i">等待推送…</span></div>
  </div>
  <div class="foot">心跳 30s · 金句组 3min · 伴读组 10min · 微习惯 60min · 提醒 15min · 断线退避重试</div>
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

    # 3.5) 静坐三省页（复用原骑行页的槽位，保持页序）：呼吸引导 + 静坐计时 + 三省打卡 + 日课轮读
    XINGSHEN_HTML = """<style>
  .wrap{height:100%;box-sizing:border-box;padding:1.2vh 1.6vw;display:flex;flex-direction:column;gap:1vh}
  .top{display:flex;gap:1.2vw;flex:1;min-height:0}
  .pane{background:rgba(255,255,255,.05);border:1px solid rgba(45,212,191,.28);border-radius:14px;padding:1vh 1.2vw;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:.8vh}
  .pane.l{flex:1.1}
  .pane.r{flex:1}
  .bt{font-size:clamp(12px,2vh,20px);color:#2dd4bf;letter-spacing:.14em}
  .bwrap{position:relative;width:min(24vh,42vw);height:min(24vh,42vw);display:flex;align-items:center;justify-content:center}
  .circle{position:absolute;top:0;left:0;right:0;bottom:0;border-radius:50%;background:radial-gradient(circle,rgba(45,212,191,.35),rgba(45,212,191,.08));border:2px solid rgba(45,212,191,.5);animation:breathe 12s ease-in-out infinite;transform:translateZ(0)}
  @keyframes breathe{0%{transform:scale(.55)}33.3%{transform:scale(1)}50%{transform:scale(1)}100%{transform:scale(.55)}}
  .phase{font-size:clamp(24px,5.2vh,52px);color:#eef2f6;font-weight:700}
  .cnt{font-size:clamp(12px,2vh,20px);color:#8a94a3}
  .sitrow{display:flex;align-items:baseline;gap:1vw}
  .sitmin{font-size:clamp(28px,6vh,58px);color:#eef2f6;font-weight:700}
  .btn{font-size:clamp(14px,2.4vh,24px);color:#04211d;background:#2dd4bf;border:none;border-radius:10px;padding:.8vh 2vw;font-weight:700;cursor:pointer}
  .btn.stop{background:#f59e0b;color:#231300}
  .ex{font-size:clamp(11px,1.8vh,18px);color:#8a94a3}
  .sans{display:flex;flex-direction:column;gap:.7vh}
  .srow{display:flex;align-items:center;gap:1vw;background:rgba(45,212,191,.06);border:1px solid rgba(45,212,191,.22);border-radius:10px;padding:.7vh 1.2vw;cursor:pointer}
  .srow .box{width:clamp(16px,3vh,28px);height:clamp(16px,3vh,28px);border:2px solid #2dd4bf;border-radius:6px;flex:none;display:flex;align-items:center;justify-content:center;color:transparent;font-size:clamp(12px,2.2vh,20px);font-weight:700}
  .srow.on .box{background:#2dd4bf;color:#04211d}
  .srow.on{background:rgba(45,212,191,.16)}
  .srow .tx{font-size:clamp(13px,2.4vh,24px);color:#eef2f6}
  .foot{background:rgba(245,158,11,.08);border:1px solid rgba(245,158,11,.3);border-radius:10px;padding:.7vh 1.4vw;display:flex;flex-direction:column;gap:.3vh}
  .foot .fk{font-size:clamp(10px,1.7vh,17px);color:#f59e0b;letter-spacing:.12em}
  .foot .fv{font-size:clamp(15px,2.8vh,28px);color:#eef2f6}
</style>
<div class="wrap">
  <div class="top">
    <div class="pane l">
      <div class="bt">主敬 · 呼吸引导</div>
      <div class="bwrap"><div class="circle"></div><div class="phase" id="ph">吸</div></div>
      <div class="cnt">吸 4s · 屏 2s · 呼 6s · 一息 12 秒</div>
    </div>
    <div class="pane r">
      <div class="bt">静坐 · 体验来复</div>
      <div class="sitrow"><span class="sitmin" id="sitmin">0</span><span class="ex">分钟</span></div>
      <div class="ex" id="sittoday">今日累计 0 分钟</div>
      <button class="btn" id="sitbtn">▶ 起坐计时</button>
    </div>
  </div>
  <div class="sans">
    <div class="srow" data-i="0"><span class="box">✓</span><span class="tx">为人谋而不忠乎？——尽心曰忠</span></div>
    <div class="srow" data-i="1"><span class="box">✓</span><span class="tx">与朋友交而不信乎？——践诺曰信</span></div>
    <div class="srow" data-i="2"><span class="box">✓</span><span class="tx">传不习乎？——温习曰学</span></div>
  </div>
  <div class="foot"><div class="fk">日课轮读</div><div class="fv" id="rike">主敬 · 整齐严肃，心不散乱</div></div>
</div>
<script>
  var RIKES=["主敬 · 整齐严肃，心不散乱","静坐 · 每日四刻，体验来复","早起 · 黎明即起，醒后勿恋","读书不二 · 一书未完不看他书","读史 · 每日圈点十叶","谨言 · 刻刻留心，第一工夫","养气 · 气藏丹田，无不可对人言","保身 · 节劳、节欲、节饮食","日知所亡 · 记录当日心得","月无忘所能 · 每月作诗文数首","作字 · 早饭后临帖半小时","夜不出门 · 戒旷功疲神"];
  setInterval(function(){var s=(Date.now()/1000)%12;document.getElementById('ph').textContent=s<4?'吸':(s<6?'屏':'呼');},400);
  var ri=0;setInterval(function(){ri=(ri+1)%RIKES.length;var e=document.getElementById('rike');var n=e.cloneNode(false);n.textContent=RIKES[ri];e.parentNode.replaceChild(n,e);},15000);
  var K='zc_sit_';function today(){var d=new Date();return d.getFullYear()+'-'+(d.getMonth()+1)+'-'+d.getDate();}
  var running=false,t0=0,tmr=null;
  function painted(){var m=parseInt(localStorage.getItem(K+today())||'0',10);document.getElementById('sittoday').textContent='今日累计 '+m+' 分钟';}
  document.getElementById('sitbtn').addEventListener('click',function(){
    var b=document.getElementById('sitbtn');
    if(!running){running=true;t0=Date.now();b.textContent='⏸ 收坐记钟';b.className='btn stop';
      tmr=setInterval(function(){document.getElementById('sitmin').textContent=Math.floor((Date.now()-t0)/60000);},5000);}
    else{running=false;clearInterval(tmr);var mins=Math.max(1,Math.round((Date.now()-t0)/60000));
      var key=K+today();localStorage.setItem(key,(parseInt(localStorage.getItem(key)||'0',10)+mins)+'');
      document.getElementById('sitmin').textContent='0';b.textContent='▶ 起坐计时';b.className='btn';painted();}
  });
  var day=today();
  document.querySelectorAll('.srow').forEach(function(r){
    var i=r.getAttribute('data-i'),k=K+'sans_'+day+'_'+i;
    if(localStorage.getItem(k)==='1')r.classList.add('on');
    r.addEventListener('click',function(){
      if(r.classList.contains('on')){r.classList.remove('on');localStorage.removeItem(k);}
      else{r.classList.add('on');localStorage.setItem(k,'1');}
    });
  });
  painted();
</script>"""
    ride_old = next((p for p in pages if p.get("id") == "ride"), None)
    if ride_old is not None:
        ride_old["widgets"] = []  # 清掉骑行四件套，槽位复用为静坐三省
    upsert_page(pages, "ride", "静坐三省", "🧘", [{
        "id": "xingshen-main", "type": "html", "x": 0, "y": 0, "w": 12, "h": 6,
        "appearance": {"fontScale": 110},
        "options": {"html": XINGSHEN_HTML, "transparent": False},
    }])

    # 4) 金句页：品读模式 —— 中枢每 3 分钟推一组（10 句），组内自由翻阅，
    #    可暂停自动轮换；push 组件 nowrap 截断问题早已改 HTML 组件解决
    QUOTE_HTML = """<style>
  .wrap{height:100%;box-sizing:border-box;padding:1vh 1.8vw .8vh;display:flex;flex-direction:column;gap:.6vh}
  .t{font-size:clamp(11px,2vh,20px);color:#8a94a3;letter-spacing:.12em;display:flex;justify-content:space-between;align-items:center}
  .badge{font-size:clamp(10px,1.7vh,17px);color:#2dd4bf;letter-spacing:0;white-space:nowrap}
  .v{flex:1;min-height:0;font-size:min(11.5vh,6.6vw);line-height:1.35;color:#eef2f6;overflow-wrap:break-word;word-break:break-word;font-weight:400;transform:translateZ(0);display:flex;align-items:center}
  .s{font-size:clamp(13px,2.8vh,26px);color:#8a94a3;overflow-wrap:break-word;word-break:break-word}
  .ctr{display:flex;gap:1vw;padding-top:.4vh}
  .btn{flex:1;height:clamp(34px,5.5vh,52px);border-radius:10px;border:1px solid rgba(45,212,191,.4);background:rgba(45,212,191,.10);color:#2dd4bf;font-size:clamp(13px,2.3vh,22px);display:flex;align-items:center;justify-content:center;user-select:none;-webkit-user-select:none;-webkit-tap-highlight-color:transparent}
  .btn:active{background:rgba(45,212,191,.28)}
  .btn.on{background:rgba(245,158,11,.18);border-color:rgba(245,158,11,.5);color:#f59e0b}
</style>
<div class="wrap">
  <div class="t"><span>QUOTE · 每日金句</span><span class="badge" id="qb">—</span></div>
  <div class="v"><span id="qv">等待推送…</span></div>
  <div class="s" id="qs"></div>
  <div class="ctr">
    <div class="btn" id="bPrev">‹ 上句</div>
    <div class="btn" id="bPause">⏸ 暂停轮换</div>
    <div class="btn" id="bNext">下句 ›</div>
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
    put('qv',it.text||'—');
    put('qs',(it.tag?'主题：'+it.tag+' · ':'')+(it.genre?it.genre+' · ':'')+it.source);
    put('qb','组内 '+(bi+1)+'/'+L+(paused?' · 已暂停':''));
  }
  function grab(){
    var p=(window.phonebox&&phonebox.data&&phonebox.data.push)||{};
    var d=p['quote-batch'];
    if(d&&d.data&&d.data.batch_no!==bn){bn=d.data.batch_no;batch=d.data;bi=0;
      if(!paused)render();else put('qb','新组已到 · 已暂停');return;}
    if(!batch){var s=p['daily-quote'];if(s&&s.data){put('qv',s.data.value||'—');put('qs',s.data.sub||'');put('qb','单条模式');}}
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
    rike = next((p for p in pages if p.get("id") == "rike"), None)
    if rike:
        # 去重：清掉历次部署遗留的所有 quote-* 组件（quote-main / quote-foot 及 -2/-3 后缀副本）
        rike["widgets"] = [w for w in rike["widgets"]
                           if not str(w.get("id", "")).startswith("quote")]

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
