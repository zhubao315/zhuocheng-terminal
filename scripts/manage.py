#!/usr/bin/env python3
"""拙诚日课 · 统一运维入口

命令：
  python scripts/manage.py doctor    # 完整诊断（环境/数据/设备/磁盘）
  python scripts/manage.py status    # 运行状态速览
  python scripts/manage.py start     # 后台启动中枢
  python scripts/manage.py stop      # 停止中枢
  python scripts/manage.py restart   # 重启
  python scripts/manage.py backup    # 备份数据与记录到 backups/
  python scripts/manage.py install   # 部署面板页面到手机（等价 setup_overview + companion --setup）
"""
import json
import os
import subprocess
import sys
import time
import urllib.request
import zipfile
from datetime import datetime
from pathlib import Path

BASE = Path(__file__).resolve().parent
# 兼容两种布局：仓库 scripts/manage.py 与工作区根 manage.py
if (BASE / "daily_hub.py").exists():
    SCRIPTS = BASE
else:
    SCRIPTS = BASE / "scripts"
DATA_DIR = Path(os.environ.get("PHONEBOX_DATA_DIR", SCRIPTS.parent / "data"))
API = os.environ.get("PHONEBOX_API", "http://127.0.0.1:8765")
sys.path.insert(0, str(SCRIPTS))


def hub_pid():
    p = DATA_DIR / ".hub_pid"
    if not p.exists():
        return None
    try:
        return int(p.read_text().strip())
    except ValueError:
        return None


def pid_alive(pid):
    if not pid:
        return False
    if os.name == "nt":
        try:
            import ctypes
            h = ctypes.windll.kernel32.OpenProcess(0x00100000, False, pid)
            if h:
                ctypes.windll.kernel32.CloseHandle(h)
                return True
            return False
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def api_ok(timeout=3):
    try:
        with urllib.request.urlopen(f"{API}/api/state", timeout=timeout) as r:
            return r.status == 200
    except Exception:
        return False


def cmd_doctor():
    import daily_hub
    ok = daily_hub.run_doctor(DATA_DIR)
    return 0 if ok else 1


def cmd_status():
    pid = hub_pid()
    alive = pid_alive(pid)
    print(f"中枢进程: {'运行中 pid ' + str(pid) if alive else '未运行'}")
    print(f"PhoneBox API: {'可达' if api_ok() else '不可达'}")
    rec_dir = DATA_DIR / "records"
    days = sorted(rec_dir.glob("*.json")) if rec_dir.exists() else []
    today = datetime.now().strftime("%Y-%m-%d")
    print(f"日课记录: {len(days)} 天")
    tp = rec_dir / f"{today}.json"
    if tp.exists():
        rec = json.loads(tp.read_text(encoding="utf-8"))
        print(f"今日: 金句组 {rec.get('quotes_batches', 0)} · 微习惯 {len(rec.get('habits_shown', []))} · 提醒 {len(rec.get('reminders_shown', []))} · 硬件采样 {len(rec.get('hardware', []))}")
    return 0


def cmd_start():
    pid = hub_pid()
    if pid_alive(pid):
        print(f"中枢已在运行（pid {pid}）")
        return 0
    flags = 0
    if os.name == "nt":
        flags = 0x00000008 | 0x00000200  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
    proc = subprocess.Popen(
        [sys.executable, "-X", "utf8", str(SCRIPTS / "daily_hub.py")],
        cwd=str(SCRIPTS), creationflags=flags,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
    print(f"中枢已启动 pid {proc.pid}")
    return 0


def cmd_stop():
    pid = hub_pid()
    if not pid_alive(pid):
        print("中枢未运行")
        (DATA_DIR / ".hub_pid").unlink(missing_ok=True)
        return 0
    if os.name == "nt":
        subprocess.run(["taskkill", "/PID", str(pid), "/F"], capture_output=True)
    else:
        import signal
        os.kill(pid, signal.SIGTERM)
    time.sleep(1)
    print("中枢已停止" if not pid_alive(hub_pid()) else "停止失败，请手动检查")
    return 0


def cmd_backup():
    ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    bdir = DATA_DIR / "backups"
    bdir.mkdir(exist_ok=True)
    dest = bdir / f"zhuocheng-backup-{ts}.zip"
    with zipfile.ZipFile(dest, "w", zipfile.ZIP_DEFLATED) as z:
        for name in ("quotes.json", "companion.json", "microhabits.json", "rike_reminders.json",
                     "rike_items.json", ".hub_state.json"):
            p = DATA_DIR / name
            if p.exists():
                z.write(p, name)
        rec = DATA_DIR / "records"
        if rec.exists():
            for f in rec.glob("*.json"):
                z.write(f, f"records/{f.name}")
    print(f"已备份 {len(zipfile.ZipFile(dest).namelist())} 个文件 → {dest}")
    return 0


def cmd_install():
    for script, arg in (("setup_overview.py", None), ("ai_companion.py", "--setup")):
        r = subprocess.run([sys.executable, "-X", "utf8", str(SCRIPTS / script)] + ([arg] if arg else []),
                           cwd=str(SCRIPTS))
        if r.returncode:
            print(f"⚠ {script} 部署返回 {r.returncode}")
    print("部署完成（install 前建议先 backup）")
    return 0


def main():
    cmds = {"doctor": cmd_doctor, "status": cmd_status, "start": cmd_start,
            "stop": cmd_stop, "restart": lambda: (cmd_stop(), cmd_start())[1],
            "backup": cmd_backup, "install": cmd_install}
    if len(sys.argv) < 2 or sys.argv[1] not in cmds:
        print("用法: python scripts/manage.py " + "|".join(cmds))
        return 1
    return cmds[sys.argv[1]]()


if __name__ == "__main__":
    sys.exit(main())
