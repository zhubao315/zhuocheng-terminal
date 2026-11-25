#!/usr/bin/env python3
"""拙诚日课终端 · 定时中枢 v2（调度解耦版）

设计原则（对应 docs/04 审计报告的 P0 整改）：
  1. 心跳 / 内容轮换 / 硬件采集解耦为独立任务，各拥独立周期（不再绑在同一个 10 秒循环）。
  2. 只推变化：每个推送键维护内容哈希，内容没变不重发。
  3. 时段感知：早晨推立志/求知，白天推谨言/笃行，傍晚推自省，深夜推恬静。
  4. 品读模式：金句按「组」推送（每组 10 句，页面内可暂停/上下切换），不再 10 秒强制换。
  5. 日课历史落盘：records/YYYY-MM-DD.json 每日独立记录，绝不覆盖历史。
  6. 可靠运行：单实例保护、断线指数退避、日志轮转、优雅退出。

任务周期（全部可用环境变量覆盖，默认为日常模式）：
  HEARTBEAT_INTERVAL     心跳           30 秒
  QUOTE_INTERVAL         金句组轮换      180 秒（每组 10 句，页面内自由翻阅）
  COMPANION_INTERVAL     伴读组轮换      600 秒（每组 5 条）
  MICROHABIT_INTERVAL    微习惯          3600 秒
  HARDWARE_INTERVAL      硬件采集        120 秒
  REMINDER_INTERVAL      日课提醒        900 秒
  DISPLAY_MODE           daily | demo（demo：金句 10 秒、伴读 30 秒，演示用）

面板组件需要的 key：
  daily-quote   金句（兼容单条）  quote-batch  金句组（10 句，品读模式数据源）
  quote-meta    金句语境          quote-hour   时辰宜事
  companion-batch 伴读组（5 条）  rike-reminder 日课提醒
  micro-habit   今日微习惯        phone-batt   手机电量
  phone-sensor  环境感知          hub-info     中枢心跳

用法：
  python daily_hub.py                # 常驻（默认）
  python daily_hub.py --once         # 推一轮
  python daily_hub.py --dry-run      # 只算不推（不写状态/记录）
  python daily_hub.py --check        # 快速体检（环境+数据）
  python daily_hub.py --doctor       # 完整诊断
  python daily_hub.py --demo         # 演示节奏（金句10s/伴读30s）
  python daily_hub.py --verbose      # DEBUG 日志
  python daily_hub.py --version      # 版本号
"""
import argparse
import json
import logging
import os
import random
import subprocess
import sys
import time
import urllib.request
from collections import deque
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

VERSION = "2.0.0"

BASE = Path(__file__).resolve().parent


def _env(name, default, cast=str):
    v = os.environ.get(name)
    return cast(v) if v not in (None, "") else default


CFG = {
    "api": _env("PHONEBOX_API", "http://127.0.0.1:8765"),
    "adb": _env("PHONEBOX_ADB", "adb"),
    "wifi": _env("PHONEBOX_WIFI_ADB", "192.168.1.66:5555"),
    "device_serial": _env("PHONEBOX_DEVICE_SERIAL", ""),
    "data_dir": Path(_env("PHONEBOX_DATA_DIR", str(BASE.parent / "data"))),
    "heartbeat": _env("HEARTBEAT_INTERVAL", 30, int),
    "quote": _env("QUOTE_INTERVAL", 180, int),
    "companion": _env("COMPANION_INTERVAL", 600, int),
    "microhabit": _env("MICROHABIT_INTERVAL", 3600, int),
    "hardware": _env("HARDWARE_INTERVAL", 120, int),
    "reminder": _env("REMINDER_INTERVAL", 900, int),
    "display_mode": _env("DISPLAY_MODE", "daily"),
    "log_level": _env("LOG_LEVEL", "INFO"),
}
QUOTE_BATCH_SIZE = 10
COMPANION_BATCH_SIZE = 5
QUOTE_KEY = "daily-quote"
QUOTE_BATCH_KEY = "quote-batch"
QUOTE_META_KEY = "quote-meta"
QUOTE_HOUR_KEY = "quote-hour"
COMPANION_BATCH_KEY = "companion-batch"
RIKE_KEY = "rike-reminder"
BATT_KEY = "phone-batt"
SENSOR_KEY = "phone-sensor"
MICRO_KEY = "micro-habit"
INFO_KEY = "hub-info"

START_T = time.time()
log = logging.getLogger("hub")

# ---------------------------------------------------------------- 时段感知
# (起始小时, 结束小时不含, 名称, 偏好主题集合)
PERIODS = [
    (5, 11, "晨读", {"立志", "求知", "行动", "惜时", "恒"}),
    (11, 14, "午间", {"拙诚", "谨言", "觉察", "养气"}),
    (14, 18, "午后", {"行动", "谨言", "欲望", "保身", "拙诚"}),
    (18, 22, "傍晚", {"自省", "恬静", "独处", "养气", "爱"}),
    (22, 24, "夜静", {"恬静", "觉察", "无常", "空性"}),
    (0, 5, "夜静", {"恬静", "觉察", "无常", "空性"}),
]


def period_name(hour=None):
    h = datetime.now().hour if hour is None else hour
    for a, b, name, _ in PERIODS:
        if a <= h < b:
            return name
    return "夜静"


def period_tags(hour=None):
    h = datetime.now().hour if hour is None else hour
    for a, b, _, tags in PERIODS:
        if a <= h < b:
            return tags
    return set()


# ---------------------------------------------------------------- 金句主题
TAG_RULES = [
    (("空性", "皆空", "色即是空", "五蕴", "无住", "无相", "妄", "缘起", "不生不灭"), "空性"),
    (("无常", "刹那", "逝", "流年", "白驹", "代谢", "生死", "光阴"), "无常"),
    (("当下", "此刻", "现在", "息", "观", "觉", "念"), "觉察"),
    (("静", "定", "坐", "虚", "安"), "恬静"),
    (("忧", "惧", "怕", "焦", "烦"), "焦虑"),
    (("言", "语", "说", "辩", "口"), "谨言"),
    (("学", "读", "书", "知", "问", "思"), "求知"),
    (("恒", "常久", "有恒", "专", "不二", "积"), "恒"),
    (("诚", "拙", "实", "伪", "巧"), "拙诚"),
    (("志", "立", "愿", "向"), "立志"),
    (("行", "为", "做", "事", "勤", "勉"), "行动"),
    (("欲", "贪", "俭", "廉", "物"), "欲望"),
    (("身", "体", "睡", "早", "食", "饮", "步", "养生", "劳"), "保身"),
    (("气", "忍", "怒", "平"), "养气"),
    (("独", "慎独", "处"), "独处"),
    (("爱", "仁", "善", "慈", "恩"), "爱"),
    (("时", "日", "月", "年", "春", "秋", "晨", "夜"), "惜时"),
    (("过", "错", "省", "改"), "自省"),
]

GENRE_RULES = [
    (("金刚经", "中论", "坛经", "八大人觉经", "佛"), "佛家经典"),
    (("道德经", "庄子", "老", "道"), "道家经典"),
    (("论语", "孟子", "大学", "中庸", "朱子", "孔", "孟"), "儒家经典"),
    (("曾国藩", "了凡", "菜根", "小窗", "围炉", "呻吟", "增广", "传习"), "明清格言"),
    (("周易", "荀子", "孙子", "史记", "诗经", "古诗", "礼记", "左传"), "上古诗文"),
    (("飞鸟集", "苏轼", "陶渊明", "王维", "李白", "杜甫", "刘禹锡", "李清照", "辛弃疾", "陆游", "王安石"), "古典诗词"),
    (("拙诚原创", "原创"), "拙诚原创"),
    (("转写", "冥想", "简史", "疲劳", "绿灯", "爱情课", "焦虑的人"), "现代转写"),
]


def quote_tag(text):
    for keys, tag in TAG_RULES:
        if any(k in text for k in keys):
            return tag
    return "澄心"


def quote_genre(source):
    for keys, g in GENRE_RULES:
        if any(k in source for k in keys):
            return g
    return "公版经典"


def pick_quotes(quotes, n, recent, hour=None, tag_cache=None):
    """时段感知选句：优先当前时段偏好主题，排除近期已推，凑不满则降级全池。
    返回索引列表（长度 ≤ n）。"""
    tag_cache = tag_cache if tag_cache is not None else {}
    prefs = period_tags(hour)
    recent = set(recent)
    all_idx = [i for i in range(len(quotes)) if i not in recent]
    pref_idx = []
    for i in all_idx:
        t = tag_cache.get(i)
        if t is None:
            t = quote_tag(quotes[i]["text"])
            tag_cache[i] = t
        if t in prefs:
            pref_idx.append(i)
    random.shuffle(pref_idx)
    chosen = pref_idx[:n]
    if len(chosen) < n:
        rest = [i for i in all_idx if i not in chosen]
        random.shuffle(rest)
        chosen += rest[: n - len(chosen)]
    return chosen


# ---------------------------------------------------------------- 硬件
def ensure_wifi_device():
    try:
        r = subprocess.run([CFG["adb"], "devices"], capture_output=True, text=True, timeout=5)
        if any(line.strip().endswith("\tdevice") for line in r.stdout.splitlines()[1:]):
            return
        subprocess.run([CFG["adb"], "connect", CFG["wifi"]], capture_output=True, text=True, timeout=5)
    except Exception:
        pass


def adb(*args):
    """所有 adb shell 统一带 -s 目标设备；未指定时才走 adb 默认选择。"""
    serial = CFG["device_serial"] or device_serial()
    cmd = [CFG["adb"]] + (["-s", serial] if serial else []) + ["shell", *args]
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=8)
        return r.stdout.strip()
    except Exception:
        return ""


def device_serial():
    try:
        r = subprocess.run([CFG["adb"], "devices"], capture_output=True, text=True, timeout=5)
        online = set()
        for line in r.stdout.splitlines()[1:]:
            line = line.strip()
            if line.endswith("\tdevice"):
                online.add(line.split("\t")[0])
        want = CFG["device_serial"]
        if want:
            return want if want in online else None  # 指定设备不在线 → 绝不回退到别的设备
        if len(online) == 1:
            return next(iter(online))
        if len(online) > 1:
            log.warning("检测到 %s 台设备，请设置 PHONEBOX_DEVICE_SERIAL 指定目标", len(online))
    except Exception:
        pass
    return None


def read_battery():
    d = {}
    for line in adb("dumpsys", "battery").splitlines():
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
    light = "?"
    for line in out.splitlines():
        if "LIGHT:" in line and "last" in line:
            parts = line.split("last", 1)[1]
            nums = [x for x in parts.replace("(", " ").replace(")", " ").split() if x.replace(".", "").isdigit()]
            if nums:
                light = f"{float(nums[0]):.0f} lux"
            break
    screen = adb("dumpsys", "power", "|", "grep", "-m1", "mWakefulness=")
    screen = screen.split("mWakefulness=")[-1].strip() if "mWakefulness=" in screen else "?"
    bright = adb("settings", "get", "system", "screen_brightness")
    return light, screen, bright


# ---------------------------------------------------------------- 推送（变更检测）
class Pusher:
    """带内容哈希的推送器：内容没变不重发；dry_run 只记录不发送。"""

    def __init__(self, api, dry_run=False):
        self.api = api
        self.dry_run = dry_run
        self.last_hash = {}
        self._fail_streaks = {}          # 每个推送键独立退避，互不掩盖
        self.dry_log = []

    @property
    def fail_streak(self):
        return max(self._fail_streaks.values(), default=0)

    @fail_streak.setter
    def fail_streak(self, value):
        self._fail_streaks = {"*": value}

    def push(self, key, payload, force=False):
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True)
        h = hash(body)
        if not force and self.last_hash.get(key) == h:
            return True  # 内容未变，跳过
        if self.dry_run:
            self.dry_log.append((key, payload.get("value", "")[:30]))
            self.last_hash[key] = h
            return True
        try:
            req = urllib.request.Request(
                f"{self.api}/api/push/{key}",
                data=body.encode("utf-8"),
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as r:
                ok = r.status == 200
        except Exception:
            ok = False
        if ok:
            self.last_hash[key] = h
            self._fail_streaks[key] = 0
        else:
            self._fail_streaks[key] = self._fail_streaks.get(key, 0) + 1
        return ok

    def backoff(self, base, key=None):
        """API 连续失败时放大等待（最多 4 倍）；按推送键独立计数。"""
        streak = (self._fail_streaks.get(key, 0) if key else self.fail_streak)
        return base * min(2 ** streak, 4) if streak else base


# ---------------------------------------------------------------- 每日记录
class DailyRecords:
    """records/YYYY-MM-DD.json，每天一个独立文件，只增不覆盖。"""

    CAPS = {"hardware": 48, "reminders_shown": 16, "habits_shown": 16, "events": 32}

    def __init__(self, data_dir, dry_run=False):
        self.dir = Path(data_dir) / "records"
        self.dry_run = dry_run
        self._cache_path = None
        self._cache = None

    def _load(self, day):
        path = self.dir / f"{day}.json"
        if self._cache_path == path and self._cache is not None:
            return self._cache, path
        if path.exists():
            try:
                rec = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                rec = {"date": day}
        else:
            rec = {"date": day}
        rec.setdefault("quotes_batches", 0)      # 当日金句组数（跨日归零）
        rec.setdefault("quote_items_sent", 0)    # 当日成功送达的金句条数
        rec.setdefault("quotes_read", 0)         # 兼容旧字段
        rec.setdefault("habits_shown", [])
        rec.setdefault("reminders_shown", [])
        rec.setdefault("hardware", [])
        rec.setdefault("events", [])
        rec.setdefault("checklist_note", "打卡状态存于手机端，Agent 接口未提供回读（见审计报告 P1-3）")
        self._cache_path, self._cache = path, rec
        return rec, path

    def update(self, **fields):
        day = datetime.now().strftime("%Y-%m-%d")
        rec, path = self._load(day)
        lists = {"habits_shown", "reminders_shown", "hardware", "events"}
        for k, v in fields.items():
            if k in lists:
                rec[k].append(dict(v, t=datetime.now().strftime("%H:%M")))
                if len(rec[k]) > self.CAPS[k]:
                    rec[k] = rec[k][-self.CAPS[k]:]
            else:
                rec[k] = v
        if not self.dry_run:
            self._save(rec, path)
        return rec

    @staticmethod
    def _save(rec, path):
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
        os.replace(tmp, path)


# ---------------------------------------------------------------- 时辰宜事
HOUR_RITES = [
    (5,  "卯时 · 晨读", "宜立志", "一日之计：先定下今天最重要的那一件事"),
    (8,  "辰时 · 佐餐", "宜进学", "读书不二：手头这本，读进去就是收获"),
    (12, "午时 · 亭午", "宜养神", "闭目片刻，让心回到原位再继续"),
    (14, "未时 · 日昳", "宜省身", "回看半日言行：哪一句可以不说？哪一步可以更实？"),
    (18, "酉时 · 日入", "宜动身", "散步、拉伸——身体动起来，气就顺了"),
    (20, "戌时 · 掌灯", "宜笔墨", "写几个字、记一句心得，给今天留个凭据"),
    (22, "亥时 · 人定", "宜安歇", "放下屏幕，明日之事交给明早的你"),
]


def hour_rite():
    h = datetime.now().hour
    chosen = HOUR_RITES[-1]
    for item in HOUR_RITES:
        if h >= item[0]:
            chosen = item
    return chosen[1], chosen[2], chosen[3]


# ---------------------------------------------------------------- 语料缓存（mtime 感知）
class Corpus:
    def __init__(self, data_dir):
        self.dir = Path(data_dir)
        self._cache = {}

    def _load(self, name):
        path = self.dir / name
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return None
        c = self._cache.get(name)
        if c and c[0] == mtime:
            return c[1]
        try:
            data = json.loads(path.read_text(encoding="utf-8"))["items"]
        except Exception as e:
            log.warning("语料加载失败 %s: %s", name, e)
            return c[1] if c else None
        self._cache[name] = (mtime, data)
        return data

    def quotes(self):
        return self._load("quotes.json") or []

    def habits(self):
        return self._load("microhabits.json") or []

    def reminders(self):
        return self._load("rike_reminders.json") or []

    def companions(self):
        # 与金句一样从本 Corpus 的 data_dir 读取，避免受全局 DATA_DIR/测试环境漂移影响
        return self._load("companion.json") or []


# ---------------------------------------------------------------- 状态与单实例
def load_state(path):
    try:
        return json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return {"pushes": {}}


def save_state(path, s):
    Path(path).write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")


def _pid_alive(pid):
    if pid <= 0:
        return False
    if os.name == "nt":
        try:
            import ctypes
            SYNCHRONIZE = 0x00100000
            k = ctypes.windll.kernel32
            h = k.OpenProcess(SYNCHRONIZE, False, pid)
            if h:
                k.CloseHandle(h)
                return True
            return False
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def acquire_single_instance(pid_path):
    """返回 True=获得运行权；False=已有实例在跑。"""
    p = Path(pid_path)
    if p.exists():
        try:
            old = int(p.read_text().strip() or 0)
        except ValueError:
            old = 0
        if old and old != os.getpid() and _pid_alive(old):
            return False
    p.write_text(str(os.getpid()), encoding="utf-8")
    return True


def fmt_uptime():
    s = int(time.time() - START_T)
    if s < 3600:
        return f"{s // 60}m{s % 60:02d}s"
    return f"{s // 3600}h{(s % 3600) // 60:02d}m"


# ---------------------------------------------------------------- 诊断
def run_check(data_dir, verbose=False):
    """快速体检：数据文件 + 配置。返回是否全部通过。"""
    data_dir = Path(data_dir)
    ok = True
    for name, want in (("quotes.json", 999), ("companion.json", 999), ("microhabits.json", 30), ("rike_reminders.json", 12)):
        p = data_dir / name
        try:
            n = len(json.loads(p.read_text(encoding="utf-8"))["items"])
            tag = "OK" if n >= want else f"不足(期望≥{want})"
            ok &= n >= want
        except Exception as e:
            n, tag = "-", f"缺失/损坏: {e}"
            ok = False
        print(f"  [{'√' if 'OK' == tag else '×'}] {name:22s} {n} 条 {tag if 'OK' != tag else ''}")
    adb_ok = Path(CFG["adb"]).exists() if os.path.isabs(CFG["adb"]) else True
    print(f"  [{'√' if adb_ok else '×'}] adb 路径 {CFG['adb'] if adb_ok else '不存在'}")
    api_ok = False
    try:
        with urllib.request.urlopen(f"{CFG['api']}/api/state", timeout=3) as r:
            api_ok = r.status == 200
    except Exception:
        pass
    print(f"  [{'√' if api_ok else '×'}] PhoneBox API {CFG['api']}" + ("" if api_ok else " 不可达（中枢可离线运行，仅推送暂停）"))
    print(f"  节奏: 心跳{CFG['heartbeat']}s 金句组{CFG['quote']}s 伴读组{CFG['companion']}s 微习惯{CFG['microhabit']}s 硬件{CFG['hardware']}s 提醒{CFG['reminder']}s 模式={CFG['display_mode']}")
    return ok


def run_doctor(data_dir):
    """完整诊断：体检 + 设备 + 记录目录 + 磁盘。"""
    print("== 拙诚日课终端 · 诊断 ==")
    print(f"版本 {VERSION} · Python {sys.version.split()[0]} · 平台 {sys.platform}")
    data_dir = Path(data_dir)
    ok = run_check(data_dir)
    rec_dir = data_dir / "records"
    days = sorted(rec_dir.glob("*.json")) if rec_dir.exists() else []
    print(f"  [{'√' if days else '·'}] 日课记录 {len(days)} 天（最新：{days[-1].stem if days else '无'}）")
    if days:
        try:
            rec = json.loads(days[-1].read_text(encoding="utf-8"))
            print(f"      最新记录摘要: 金句组 {rec.get('quotes_batches', 0)} · 微习惯 {len(rec.get('habits_shown', []))} · 硬件采样 {len(rec.get('hardware', []))}")
        except Exception as e:
            print(f"      记录损坏: {e}")
            ok = False
    serial = device_serial()
    if serial:
        print(f"  [√] 设备在线 {serial} ({'WiFi' if ':' in serial else 'USB'})")
    else:
        ensure_wifi_device()
        serial = device_serial()
        print(f"  [{'√' if serial else '×'}] 设备 {'在线 ' + serial if serial else '离线（推送将退避重试）'}")
    import shutil
    free_gb = shutil.disk_usage(data_dir).free / 1e9
    disk_ok = free_gb > 0.5
    print(f"  [{'√' if disk_ok else '×'}] 磁盘剩余 {free_gb:.1f} GB")
    pid_p = data_dir / ".hub_pid"
    if pid_p.exists():
        try:
            old = int(pid_p.read_text().strip())
            alive = _pid_alive(old)
            if alive:
                print(f"  [√] 中枢实例: pid {old} 运行中")
            else:
                print(f"  [·] 中枢实例: pid {old} 已退出（残留 pid 文件将自动清理）")
        except Exception:
            print("  [·] pid 文件损坏")
    print("诊断完成" + ("，全部通过" if ok else "，存在未通过项"))
    return ok


# ---------------------------------------------------------------- 主循环
class Hub:
    def __init__(self, dry_run=False):
        self.data_dir = CFG["data_dir"]
        self.pusher = Pusher(CFG["api"], dry_run=dry_run)
        self.corpus = Corpus(self.data_dir)
        self.records = DailyRecords(self.data_dir, dry_run=dry_run)
        self.state_path = self.data_dir / ".hub_state.json"
        self.state = load_state(self.state_path)
        self.state.setdefault("pushes", {})
        self.tag_cache = {}
        self.recent_quotes = deque(maxlen=20)
        self.recent_companions = deque(maxlen=15)
        self.quote_batch_no = self.state.get("quote_batch_no", 0)        # 全局累计（不用于展示）
        self.companion_batch_no = self.state.get("companion_batch_no", 0)
        self.next_run = {k: 0.0 for k in ("heartbeat", "quote", "companion", "microhabit", "hardware", "reminder")}
        self._next = {}

    # 各任务周期（demo 模式覆盖内容节奏）
    def interval(self, task):
        demo = CFG["display_mode"] == "demo"
        if task == "quote":
            return 10 if demo else CFG["quote"]
        if task == "companion":
            return 30 if demo else CFG["companion"]
        return CFG[task]

    # ---- 任务实现 ----
    def t_quote(self):
        quotes = self.corpus.quotes()
        if not quotes:
            return
        idxs = pick_quotes(quotes, QUOTE_BATCH_SIZE, self.recent_quotes, tag_cache=self.tag_cache)
        if not idxs:
            return
        self.recent_quotes.extend(idxs)
        self.quote_batch_no += 1
        items = [{"text": quotes[i]["text"], "source": quotes[i]["source"],
                  "tag": quote_tag(quotes[i]["text"]), "genre": quote_genre(quotes[i]["source"])} for i in idxs]
        ok_batch = self.pusher.push(QUOTE_BATCH_KEY,
                                    {"batch_no": self.quote_batch_no, "period": period_name(), "items": items})
        head = items[0]
        ok1 = self.pusher.push(QUOTE_KEY, {"value": head["text"], "sub": head["source"], "title": "每日金句", "icon": "quote"})
        # 全局批次号只用于 push payload；每日记录必须是当日真实组数（跨日归零）
        today_rec, _ = self.records._load(datetime.now().strftime("%Y-%m-%d"))
        daily_batches = today_rec["quotes_batches"] + 1
        delivered = ok_batch and ok1
        rec = self.records.update(
            quotes_batches=daily_batches,
            quote_items_sent=today_rec["quote_items_sent"] + (len(items) if delivered else 0),
            quotes_read=daily_batches,
            events={"event_type": "quote_batch", "item_id": self.quote_batch_no,
                    "status": "delivered" if delivered else "failed", "count": len(items)})
        self.pusher.push(QUOTE_META_KEY, {
            "value": f"主题：{head['tag']} · {head['genre']}",
            "sub": f"今日已推 {rec['quotes_batches']} 组 · 组内可自由翻阅",
            "title": "金句语境", "icon": "tag"})
        label, yi, tip = hour_rite()
        self.pusher.push(QUOTE_HOUR_KEY, {"value": f"{label} · {yi}", "sub": tip, "title": "时辰宜事", "icon": "clock"})
        self.state["quote_idx"] = idxs[0]
        self.state["quote_batch_no"] = self.quote_batch_no
        log.info("金句组#%s 今日第%s组 %s句 推%s", self.quote_batch_no, daily_batches, len(items),
                 "√" if delivered else "×")

    def records_quote_count(self):
        """当日成功送达的金句条数（不是全局批次号）。"""
        rec, _ = self.records._load(datetime.now().strftime("%Y-%m-%d"))
        return rec["quote_items_sent"]

    def t_companion(self):
        comps = self.corpus.companions()
        if not comps:
            return
        pool = [i for i in range(len(comps)) if i not in self.recent_companions]
        if len(pool) < COMPANION_BATCH_SIZE:
            pool = list(range(len(comps)))
        random.shuffle(pool)
        idxs = pool[:COMPANION_BATCH_SIZE]
        self.recent_companions.extend(idxs)
        items = []
        for i in idxs:
            c = comps[i]
            items.append({"passage": c["passage"], "source": c["source"], "insight": c["insight"],
                          "question": c["question"], "practice": c["practice"], "tag": c["tag"]})
        self.companion_batch_no += 1
        ok = self.pusher.push(COMPANION_BATCH_KEY, {"batch_no": self.companion_batch_no, "items": items})
        self.state["companion_batch_no"] = self.companion_batch_no
        log.info("伴读组#%s %s条 %s %s", self.companion_batch_no, len(items),
                 [comps[i]["source"] for i in idxs[:2]], "√" if ok else "×")

    def t_microhabit(self):
        habits = self.corpus.habits()
        if not habits:
            return
        midx = random.randrange(len(habits))
        h = habits[midx]
        minutes = h.get("duration_minutes", 2)   # 逐条标注真实时长，不再统一承诺「2 分钟」
        ok = self.pusher.push(MICRO_KEY, {
            "value": h["habit"], "sub": f"对应日课：{h['maps']} · 约 {minutes} 分钟",
            "title": "今日微习惯", "icon": "target"})
        self.records.update(
            habits_shown={"idx": midx, "name": h["habit"], "status": "delivered" if ok else "failed"},
            events={"event_type": "microhabit", "item_id": midx, "status": "delivered" if ok else "failed"})
        self.state["micro_idx"] = midx
        self.state["micro_date"] = datetime.now().strftime("%Y-%m-%d")
        log.info("微习惯[%s]%s", midx, "√" if ok else "×")

    def t_reminder(self):
        reminders = self.corpus.reminders()
        if not reminders:
            return
        ridx = random.randrange(len(reminders))
        r = reminders[ridx]
        ok = self.pusher.push(RIKE_KEY, {
            "value": f"{r['name']} · {r['remind']}",
            "sub": f"做法：{r['how']}", "title": "日课提醒", "icon": "bell"})
        self.records.update(
            reminders_shown={"idx": ridx, "name": r["name"], "status": "delivered" if ok else "failed"},
            events={"event_type": "reminder", "item_id": ridx, "status": "delivered" if ok else "failed"})
        self.state["rike_idx"] = ridx
        log.info("日课提醒[%s]%s", ridx, "√" if ok else "×")

    def t_hardware(self):
        serial = device_serial()
        if serial is None:
            ensure_wifi_device()
            serial = device_serial()
        self.conn = "WiFi adb" if serial and ":" in serial else ("USB" if serial else None)
        if not self.conn:
            log.info("设备离线，跳过硬件采集")
            return
        level, temp, status = read_battery()
        ok1 = self.pusher.push(BATT_KEY, {
            "value": f"{level}%", "sub": f"{temp} · {status}", "title": "手机电量", "icon": "battery",
            "level": "warn" if level.isdigit() and int(level) < 20 else "ok"}, force=True)
        light, screen, bright = read_sensors()
        # 三态：supported（读到真实值）/ unavailable（设备无能力）/ error（读失败），不用「?」冒充数值
        got_battery, got_light = level.isdigit(), light != "?"
        hw_status = "supported" if got_battery and got_light else (
            "error" if got_battery or got_light else "unavailable")
        label = {"supported": "已采集", "unavailable": "设备不支持", "error": "采集失败"}[hw_status]
        self.pusher.push(SENSOR_KEY, {
            "value": light if got_light else "—", "sub": f"{label} · 亮度{bright} · {screen}",
            "title": "环境感知", "icon": "light"}, force=True)
        self.records.update(hardware={"level": level, "temp": temp, "status": status,
                                      "light": light, "sensor_status": hw_status})
        self.state["last_hw"] = datetime.now().strftime("%H:%M")
        log.info("硬件 %s%% %s %s", level, temp, self.conn)

    def t_heartbeat(self):
        today = datetime.now().strftime("%Y-%m-%d")
        pushes_today = self.state["pushes"].get(today, 0) + 1
        self.state["pushes"][today] = pushes_today
        self.state["pushes"] = dict(sorted(self.state["pushes"].items())[-3:])
        quotes = self.corpus.quotes()
        habits = self.corpus.habits()
        reminders = self.corpus.reminders()
        fail_txt = f" · ⚠推送连续失败{self.pusher.fail_streak}" if self.pusher.fail_streak else ""
        today_rec, _ = self.records._load(today)
        self.pusher.push(INFO_KEY, {
            "value": f"已运行 {fmt_uptime()} · 今日心跳 {pushes_today} 次{fail_txt}",
            "sub": f"{self.conn or '设备离线'} · 今日金句 {today_rec['quotes_batches']} 组 / {today_rec['quote_items_sent']} 句 · 时段 {period_name()} · 微习惯 {(self.state.get('micro_idx', 0) + 1)}/{len(habits)} · 提醒 {(self.state.get('rike_idx', 0) + 1)}/{len(reminders)} · 硬件 {self.state.get('last_hw', '—')}",
            "title": "中枢心跳", "icon": "pulse"}, force=True)

    def run_once(self, dry=False):
        now = time.time()
        tasks = [t for t in self.next_run if now >= self.next_run[t]]
        for t in tasks:
            self.next_run[t] = now + self.interval(t)
        for t in tasks:
            fn = {"heartbeat": self.t_heartbeat, "quote": self.t_quote, "companion": self.t_companion,
                  "microhabit": self.t_microhabit, "hardware": self.t_hardware, "reminder": self.t_reminder}[t]
            try:
                fn()
            except Exception as e:
                log.exception("任务 %s 异常: %s", t, e)
        if not dry:
            save_state(self.state_path, self.state)
        return tasks

    def serve(self):
        log.info("中枢 v%s 启动：心跳%ss 金句组%ss 伴读组%ss 微习惯%ss 硬件%ss 提醒%ss 模式=%s",
                 VERSION, CFG["heartbeat"], self.interval("quote"), self.interval("companion"),
                 CFG["microhabit"], CFG["hardware"], CFG["reminder"], CFG["display_mode"])
        self.conn = None
        try:
            while True:
                self.run_once()
                base = min(CFG["heartbeat"], self.interval("quote"), self.interval("companion")) / 2
                time.sleep(max(1.0, self.pusher.backoff(base)))
        finally:
            log.info("中枢退出")


def setup_logging(verbose):
    level = logging.DEBUG if verbose else getattr(logging, CFG["log_level"].upper(), logging.INFO)
    fmt = logging.Formatter("[%(asctime)s] %(levelname)s %(message)s", "%H:%M:%S")
    root = logging.getLogger("hub")
    root.setLevel(level)
    sh = logging.StreamHandler()
    sh.setFormatter(fmt)
    root.addHandler(sh)
    fh = RotatingFileHandler(BASE / "hub.log", maxBytes=1_000_000, backupCount=2, encoding="utf-8")
    fh.setFormatter(fmt)
    root.addHandler(fh)


def main():
    ap = argparse.ArgumentParser(description="拙诚日课终端 · 定时中枢 v2")
    ap.add_argument("--once", action="store_true", help="推一轮后退出（兼容旧 once 位置参数）")
    ap.add_argument("--dry-run", action="store_true", help="只计算不推送不落盘")
    ap.add_argument("--check", action="store_true", help="快速体检")
    ap.add_argument("--doctor", action="store_true", help="完整诊断")
    ap.add_argument("--demo", action="store_true", help="演示节奏（金句10s/伴读30s）")
    ap.add_argument("--verbose", action="store_true", help="DEBUG 日志")
    ap.add_argument("--version", action="store_true", help="版本号")
    ap.add_argument("legacy", nargs="*", help="兼容：once")
    args = ap.parse_args()
    if args.version:
        print(f"zhuocheng-terminal hub v{VERSION}")
        return 0
    setup_logging(args.verbose)
    if args.demo:
        CFG["display_mode"] = "demo"
    if args.check:
        return 0 if run_check(CFG["data_dir"]) else 1
    if args.doctor:
        return 0 if run_doctor(CFG["data_dir"]) else 1
    dry = args.dry_run
    if ("once" in args.legacy) or args.once:
        hub = Hub(dry_run=dry)
        hub.conn = None
        hub.next_run = {k: 0.0 for k in hub.next_run}
        tasks = hub.run_once(dry=dry)
        if dry:
            print(f"[dry-run] 将执行 {tasks}，推送 {len(hub.pusher.dry_log)} 项：")
            for k, v in hub.pusher.dry_log:
                print(f"   {k:16s} {v}")
        else:
            print(f"已执行 {tasks}")
        return 0
    if not acquire_single_instance(CFG["data_dir"] / ".hub_pid"):
        print("已有中枢实例在运行（.hub_pid），退出。可用 python scripts/manage.py stop 先停止。")
        return 2
    hub = Hub(dry_run=dry)
    hub.conn = None
    try:
        hub.serve()
    finally:
        try:
            (CFG["data_dir"] / ".hub_pid").unlink()
        except OSError:
            pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
