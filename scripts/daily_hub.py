#!/usr/bin/env python3
"""拙诚日课终端 · 定时中枢（10 秒心跳版）

跑在电脑上，通过 adb 采集红米 Note 2 的硬件数据，推送到 PhoneBox 面板。
全部数据走本地 http://127.0.0.1:8765/api/push/<key>。

节奏：
  每 10 秒   金句随机轮换（42 条，不与上一条重复）+ 中枢心跳推送
  每 30 秒   AI 伴读随机轮换（28 条，自包含库）
  每 60 分钟 微习惯随机换一条（14 条，映射日课十二条）
  每 90 秒   硬件采集（电量/温度/光线/屏幕）

用法:
  python daily_hub.py once       # 推一轮（测试用）
  python daily_hub.py            # 常驻循环（默认）

面板组件需要的 key:
  daily-quote   金句       micro-habit  今日微习惯
  phone-batt    手机电量   phone-sensor 环境感知
  hub-info      中枢心跳（运行时长/推送计数/连接模式/轮换进度）
"""
import json
import random
import subprocess
import sys
import time
import urllib.request
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).parent
import os
DATA_DIR = Path(os.environ.get(
    "PHONEBOX_DATA_DIR",
    Path(__file__).resolve().parent.parent / "data"))

sys.path.insert(0, str(BASE))
import ai_companion  # noqa: E402  伴读推送直接复用

ADB = os.environ.get("PHONEBOX_ADB", "adb")
API = os.environ.get("PHONEBOX_API", "http://127.0.0.1:8765")
STATE = BASE / ".hub_state.json"

QUOTE_KEY = "daily-quote"
BATT_KEY = "phone-batt"
SENSOR_KEY = "phone-sensor"
MICRO_KEY = "micro-habit"
INFO_KEY = "hub-info"

LOOP_SECONDS = 10        # 心跳周期
HARDWARE_EVERY = 9       # 每 9 拍采集硬件（90 秒）
COMPANION_EVERY = 3      # 每 3 拍换伴读（30 秒）
MICRO_EVERY = 360        # 每 360 拍换微习惯（60 分钟）

# WiFi adb（拔掉数据线也能采集）。手机端已设 persist.adb.tcp.port=5555，
# 重启后自动监听，这里每拍检查并按需连接。
WIFI_ADDR = os.environ.get("PHONEBOX_WIFI_ADB", "192.168.1.66:5555")

START_T = time.time()


def ensure_wifi_device():
    """设备列表里没有任何 device 时，尝试连接 WiFi adb。"""
    try:
        r = subprocess.run([str(ADB), "devices"], capture_output=True, text=True, timeout=5)
        if any(line.strip().endswith("\tdevice") for line in r.stdout.splitlines()[1:]):
            return
        subprocess.run([str(ADB), "connect", WIFI_ADDR], capture_output=True, text=True, timeout=5)
    except Exception:
        pass


def adb(*args):
    """执行 adb shell 命令，返回 stdout。"""
    try:
        r = subprocess.run(
            [str(ADB), "shell", *args],
            capture_output=True, text=True, timeout=8,
        )
        return r.stdout.strip()
    except Exception:
        return ""


def post(key, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        f"{API}/api/push/{key}",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            return r.status == 200
    except Exception:
        return False


def read_battery():
    out = adb("dumpsys", "battery")
    d = {}
    for line in out.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            d[k.strip()] = v.strip()
    level = d.get("level", "?")
    temp = d.get("temperature", "?")
    status = {"2": "充电中", "3": "放电", "4": "未充电", "5": "满电"}.get(d.get("status"), d.get("status", "?"))
    temp_c = f"{int(temp)/10:.1f}°C" if temp.isdigit() else temp
    return level, temp_c, status


def read_sensors():
    out = adb("dumpsys", "sensorservice")
    # 取光线传感器最后一次事件值
    light = "?"
    for line in out.splitlines():
        if "LIGHT:" in line and "last" in line:
            parts = line.split("last", 1)[1]
            nums = [x for x in parts.replace("(", " ").replace(")", " ").split() if x.replace(".", "").isdigit()]
            if nums:
                light = f"{float(nums[0]):.0f} lux"
            break
    # 屏幕状态
    screen = adb("dumpsys", "power", "|", "grep", "-m1", "mWakefulness=")
    screen = screen.split("mWakefulness=")[-1].strip() if "mWakefulness=" in screen else "?"
    bright = adb("settings", "get", "system", "screen_brightness")
    return light, screen, bright


def device_serial():
    """返回在线设备 serial：带冒号是 WiFi，否则 USB；离线返回 None。"""
    try:
        r = subprocess.run([str(ADB), "devices"], capture_output=True, text=True, timeout=5)
        for line in r.stdout.splitlines()[1:]:
            line = line.strip()
            if line.endswith("\tdevice"):
                return line.split("\t")[0]
    except Exception:
        pass
    return None


def load_state():
    if STATE.exists():
        try:
            return json.loads(STATE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"round": 0, "pushes": {}}


def save_state(s):
    STATE.write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")


def fmt_uptime():
    s = int(time.time() - START_T)
    if s < 3600:
        return f"{s // 60}m{s % 60:02d}s"
    return f"{s // 3600}h{(s % 3600) // 60:02d}m"


def run_once():
    quotes = json.loads((DATA_DIR / "quotes.json").read_text(encoding="utf-8"))["items"]
    habits = json.loads((DATA_DIR / "microhabits.json").read_text(encoding="utf-8"))["items"]
    companions = ai_companion.load_companions()
    st = load_state()
    st.setdefault("pushes", {})
    st["round"] = st.get("round", 0) + 1
    today = datetime.now().strftime("%Y-%m-%d")

    log = [f"[{datetime.now():%H:%M:%S}] 第 {st['round']} 拍"]
    pushes_today = st["pushes"].get(today, 0)

    # 1) 设备在线才采集硬件数据（每 9 拍，约 90 秒；离线先尝试 WiFi adb 重连）
    serial = device_serial()
    if serial is None:
        ensure_wifi_device()
        serial = device_serial()
    conn = None
    if serial:
        conn = "WiFi adb" if ":" in serial else "USB"
    if conn and st["round"] % HARDWARE_EVERY == 1:
        level, temp, status = read_battery()
        ok1 = post(BATT_KEY, {
            "value": f"{level}%",
            "sub": f"{temp} · {status}",
            "title": "手机电量",
            "icon": "battery",
            "level": "warn" if level.isdigit() and int(level) < 20 else "ok",
        })
        light, screen, bright = read_sensors()
        ok2 = post(SENSOR_KEY, {
            "value": light,
            "sub": f"亮度{bright} · {screen}",
            "title": "环境感知",
            "icon": "light",
        })
        pushes_today += int(ok1) + int(ok2)
        log.append(f"电量{ok1} 传感{ok2}")

    # 2) 金句：每拍随机换，不与上一条重复
    qidx = st.get("quote_idx")
    pool = [i for i in range(len(quotes)) if i != qidx]
    qidx = random.choice(pool)
    qit = quotes[qidx]
    ok3 = post(QUOTE_KEY, {
        "value": qit["text"],
        "sub": qit["source"],
        "title": "每日金句",
        "icon": "quote",
    })
    st["quote_idx"] = qidx
    pushes_today += int(ok3)
    log.append(f"金句[{qidx}]{ok3}")

    # 3) AI 伴读：每 3 拍（30 秒）随机换
    if st["round"] % COMPANION_EVERY == 0:
        try:
            cidx = ai_companion.choose_index(len(companions), st.get("companion_idx"))
            ai_companion.push_companion(cidx, companions)
            st["companion_idx"] = cidx
            pushes_today += 2
            log.append(f"伴读[{cidx}]")
        except Exception as e:
            log.append(f"伴读异常 {e}")

    # 4) 微习惯：每 360 拍（60 分钟）随机换
    if st.get("micro_date") != today or st["round"] % MICRO_EVERY == 1:
        midx = random.randrange(len(habits))
        h = habits[midx]
        ok4 = post(MICRO_KEY, {
            "value": h["habit"],
            "sub": f"对应日课：{h['maps']} · 2 分钟即可",
            "title": "今日微习惯",
            "icon": "target",
        })
        st["micro_idx"] = midx
        st["micro_date"] = today
        pushes_today += int(ok4)
        log.append(f"微习惯[{midx}]{ok4}")

    # 5) 中枢心跳：每拍推运行状态
    m = st["round"] % HARDWARE_EVERY
    next_hw = (HARDWARE_EVERY - m) * LOOP_SECONDS if m else LOOP_SECONDS
    conn_txt = conn or "设备离线"
    ok5 = post(INFO_KEY, {
        "value": f"已运行 {fmt_uptime()} · 今日推送 {pushes_today} 次",
        "sub": f"{conn_txt} · 金句 {qidx + 1}/{len(quotes)} · 伴读 {st.get('companion_idx', 0) + 1}/{len(companions)} · 下次采集 {next_hw}s",
        "title": "中枢心跳",
        "icon": "pulse",
    })
    pushes_today += int(ok5)
    log.append(f"心跳{ok5}")

    st["pushes"][today] = pushes_today
    # 只保留最近 3 天计数
    st["pushes"] = dict(sorted(st["pushes"].items())[-3:])
    save_state(st)

    msg = " ".join(log)
    print(msg)
    with (BASE / "hub.log").open("a", encoding="utf-8") as f:
        f.write(msg + "\n")


def main():
    if "once" in sys.argv:
        run_once()
        return
    print(f"定时中枢启动：{LOOP_SECONDS} 秒心跳 · 金句每拍随机 · 伴读每 {COMPANION_EVERY} 拍 · 硬件每 {HARDWARE_EVERY} 拍，Ctrl+C 停止")
    while True:
        try:
            run_once()
        except Exception as e:
            print(f"拍次异常：{e}")
        time.sleep(LOOP_SECONDS)


if __name__ == "__main__":
    main()
