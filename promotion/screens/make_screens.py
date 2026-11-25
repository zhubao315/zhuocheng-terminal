"""Generate real-terminal-style screenshots using actual corpus data and PhoneBox widget styles."""
import json, os, html, random

ROOT = 'D:/tmp/workbuddy-data-cn/2026-11-23-09-54-19/phonebox/zhuocheng-terminal'
DATA = ROOT + '/data'
OUT = ROOT + '/docs/screens'
os.makedirs(OUT, exist_ok=True)

quotes = json.load(open(DATA + '/quotes.json', encoding='utf-8'))['items']
companions = json.load(open(DATA + '/companion.json', encoding='utf-8'))['items']
habits = json.load(open(DATA + '/microhabits.json', encoding='utf-8'))['items']
rike = json.load(open(DATA + '/rike_items.json', encoding='utf-8'))['items']

CSS = '''
*{margin:0;padding:0;box-sizing:border-box}
html,body{width:100%;height:100%;overflow:hidden}
body{background:#0e1116;color:#eef2f6;font-family:"Microsoft YaHei","PingFang SC",sans-serif}
.screen{position:relative;width:100%;height:100%;padding:18px 22px;display:flex;flex-direction:column;gap:14px}
.top{display:flex;justify-content:space-between;align-items:center;font-size:13px;color:#5b6676;letter-spacing:.1em}
.top b{color:#f5b45e;font-weight:700}
.top .st{display:flex;gap:12px;align-items:center}
.top .st i{width:7px;height:7px;border-radius:50%;background:#5ec8b4;display:inline-block;margin-right:4px}
.card{background:#171c24;border:1px solid #2a3342;border-radius:14px;padding:18px 22px}
.label{font-size:11px;letter-spacing:.2em;color:#5b6676;margin-bottom:8px}
.quote{font-size:clamp(28px,4.2vh,52px);line-height:1.5;font-weight:700;color:#e8d9b8;overflow-wrap:break-word}
.src{font-size:15px;color:#8a94a3;margin-top:12px}
.chip{display:inline-block;font-size:12px;padding:3px 11px;border-radius:20px;background:rgba(245,180,94,.12);color:#f5b45e}
.bar{height:3px;background:#2a3342;border-radius:2px;overflow:hidden;margin-top:14px}
.bar i{display:block;height:100%;background:#5ec8b4;width:62%}
.tools{display:flex;gap:10px;margin-top:12px}
.tools span{font-size:12px;color:#8a94a3;border:1px solid #2a3342;border-radius:8px;padding:6px 14px}
.grid{display:grid;grid-template-columns:1fr 1fr;gap:14px;flex:1;min-height:0}
.passage{font-size:clamp(22px,3.4vh,40px);line-height:1.5;font-weight:700;color:#eef2f6;overflow-wrap:break-word}
.insight{font-size:clamp(13px,1.9vh,19px);line-height:1.8;color:#c3cbd6}
.question{font-size:clamp(13px,1.9vh,19px);line-height:1.6;color:#5ec8b4;margin-top:8px}
.habit{font-size:clamp(20px,2.8vh,32px);line-height:1.4;font-weight:700;color:#eef2f6}
.meta{font-size:13px;color:#8a94a3;margin-top:8px}
.hubrow{display:flex;align-items:center;justify-content:space-between;border-left:4px solid #2dd4bf;background:rgba(255,255,255,.05);border-radius:10px;padding:12px 18px}
.hubrow.hl{border-left-color:#f59e0b}
.hubrow .k{font-size:14px;color:#8a94a3}
.hubrow .v{font-size:clamp(18px,2.5vh,28px);color:#eef2f6;font-weight:600}
.foot{font-size:12px;color:#5b6676;text-align:center;margin-top:auto}
.rike{font-size:clamp(14px,2vh,22px);line-height:1.6;color:#c3cbd6}
'''

def shell(title, body):
    return f'''<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><style>{CSS}</style></head>
<body><div class="screen">
<div class="top"><span>拙诚日课终端 · <b>{title}</b></span><span class="st"><span><i></i>离线可用</span><span>14:20</span></span></div>
{body}
<div class="foot">OFFLINE FIRST · ZERO API KEY · 日日不断</div>
</div></body></html>'''

def pick(items, n, offset=0):
    return [items[(offset + i * 37) % len(items)] for i in range(n)]

# 1. 日课金句
q = pick(quotes, 3, 0)
body = '<div class="card">' + ''.join(
    f'<div style="margin-bottom:26px"><div class="label">金句 · {html.escape(str(item["source"]))}</div>'
    f'<div class="quote">{html.escape(str(item["text"]))}</div>'
    f'<div class="src"><span class="chip">{html.escape(str(item["tag"]))}</span></div>'
    f'<div class="bar"><i style="width:{100 - idx*12}%"></i></div></div>'
    for idx, item in enumerate(q)
) + '</div><div class="tools"><span>暂停</span><span>上句</span><span>下句</span><span>999 条 · 3 分钟一组</span></div>'
open(OUT + '/01-每日金句.html', 'w', encoding='utf-8').write(shell('日课金句', body))

# 2. AI 伴读
c = companions[128]
body = f'''<div class="grid">
<div class="card"><div class="label">AI 伴读 · {html.escape(str(c["source"]))}</div>
<div class="passage">{html.escape(str(c["passage"]))}</div>
<div class="bar"><i style="width:58%"></i></div></div>
<div class="card"><div class="label">品读 · 静坐</div>
<div class="insight">{html.escape(str(c["insight"]))}</div></div>
<div class="card"><div class="label">自省一问</div>
<div class="question">{html.escape(str(c["question"]))}</div></div>
<div class="card"><div class="label">今日日课</div>
<div class="rike">{html.escape(str(rike[2]))}<br>{html.escape(str(rike[5]))}</div>
<div class="meta">10 分钟一段 · 5 段一组 · 999 条离线语料</div></div>
</div><div class="tools"><span>暂停</span><span>上段</span><span>下段</span></div>'''
open(OUT + '/02-AI伴读.html', 'w', encoding='utf-8').write(shell('AI 伴读', body))

# 3. 日课打卡
items = rike[:8]
rows = ''.join(
    f'<div class="hubrow"><span class="k">{"✓ " if i < 3 else "○ "}{html.escape(str(x))}</span>'
    f'<span class="v">{"已完成" if i < 3 else "待打卡"}</span></div>'
    for i, x in enumerate(items)
)
body = f'<div class="card"><div class="label">曾国藩日课十二条 · 触屏打卡</div>{rows}</div><div class="tools"><span>12 项日课</span><span>本地记录</span><span>每日 JSON 存根</span></div>'
open(OUT + '/03-日课打卡.html', 'w', encoding='utf-8').write(shell('日课打卡', body))

# 4. 微习惯 + 静坐三省
h = pick(habits, 4, 3)
body = f'''<div class="grid">
<div class="card"><div class="label">微习惯 · 第 04 / 30 条</div>
<div class="habit">{html.escape(str(h[0]["habit"]))}</div>
<div class="meta">主敬 · 2 分钟 · 每日 · 完成后才打卡</div>
<div class="bar"><i style="width:100%"></i></div></div>
<div class="card"><div class="label">静坐三省 · 定时提醒</div>
<div class="rike">每日定时静默提醒<br>抬头，回到自己。<br><br>反省：今日是否主敬？<br>是否拙诚？日课是否不断？</div></div>
<div class="card"><div class="label">下一条预告</div>
<div class="habit" style="font-size:clamp(18px,2.4vh,26px)">{html.escape(str(h[1]["habit"]))}</div>
<div class="meta">{html.escape(str(h[1]["duration_minutes"]))} 分钟 · {html.escape(str(h[1]["category"]))}</div></div>
<div class="card"><div class="label">今日进度</div>
<div class="hubrow hl"><span class="k">微习惯</span><span class="v">3 / 12</span></div>
<div class="hubrow"><span class="k">静坐三省</span><span class="v">2 / 4</span></div></div>
</div>'''
open(OUT + '/04-微习惯静坐.html', 'w', encoding='utf-8').write(shell('微习惯 · 静坐三省', body))

# 5. 定时中枢
body = f'''<div class="card"><div class="label">定时中枢 · 离线节奏</div>
<div class="hubrow hl"><span class="k">今日金句</span><span class="v">{html.escape(str(quotes[7]["text"]))}</span></div>
<div class="hubrow"><span class="k">今日微习惯</span><span class="v">{html.escape(str(habits[4]["habit"]))}</span></div>
<div class="hubrow"><span class="k">伴读进度</span><span class="v">第 3 / 5 段</span></div>
<div class="hubrow"><span class="k">中枢心跳</span><span class="v">30s · 正常</span></div>
<div class="meta">金句 180s · 伴读 600s · 微习惯 3600s · 提醒 900s · 设备离线时轮播照常</div></div>
<div class="tools"><span>离线运行</span><span>无需 API Key</span><span>本地记录</span></div>'''
open(OUT + '/05-定时中枢.html', 'w', encoding='utf-8').write(shell('定时中枢', body))

print('generated 5 screens in', OUT)
