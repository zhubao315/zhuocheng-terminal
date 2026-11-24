#!/usr/bin/env python3
"""拙诚日课终端 · 中枢单元测试（不依赖真机）

运行： python -X utf8 -m unittest discover tests -v
"""
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
# 优先仓库布局 scripts/，兼容工作区布局（daily_hub.py 与 tests/ 同级）
for cand in (TESTS_DIR.parent / "scripts", TESTS_DIR.parent):
    if (cand / "daily_hub.py").exists():
        sys.path.insert(0, str(cand))
        break

_TMP = tempfile.mkdtemp(prefix="zc-test-")
os.environ["PHONEBOX_DATA_DIR"] = _TMP
os.environ.setdefault("PHONEBOX_API", "http://127.0.0.1:9")  # 测试不指向真实 API

import daily_hub as dh  # noqa: E402


def fake_quotes(specs):
    return [{"text": t, "source": s} for t, s in specs]


class TestQuoteTag(unittest.TestCase):
    def test_known_tags(self):
        self.assertEqual(dh.quote_tag("读书不二：一书未完不看他书"), "求知")
        self.assertEqual(dh.quote_tag("先静之，再思之，五六分把握即做之"), "恬静")
        self.assertEqual(dh.quote_tag(" Past".strip() + "无恒则终事无成"), "恒")

    def test_fallback(self):
        self.assertEqual(dh.quote_tag("无关键词的一句"), "澄心")


class TestPeriod(unittest.TestCase):
    def test_period_names(self):
        self.assertEqual(dh.period_name(7), "晨读")
        self.assertEqual(dh.period_name(15), "午后")
        self.assertEqual(dh.period_name(23), "夜静")
        self.assertEqual(dh.period_name(3), "夜静")

    def test_period_tags(self):
        self.assertIn("立志", dh.period_tags(7))
        self.assertIn("恬静", dh.period_tags(23))


class TestPickQuotes(unittest.TestCase):
    Q = fake_quotes([
        ("一日之计在于晨，立志要早", "曾国藩"),
        ("读书不二：一书未完不看他书", "曾国藩"),
        ("静坐然后知平日之气浮", "曾国藩"),
        ("花看半开，酒饮微醺", "菜根谭"),
        ("慎独则心安", "曾国藩"),
        ("岁月不居，时节如流", "孔融"),
    ])

    def test_recent_excluded(self):
        chosen = dh.pick_quotes(self.Q, 3, recent=[0, 1, 2, 3, 4], hour=7)
        self.assertTrue(set(chosen).isdisjoint({0, 1, 2, 3, 4}))
        self.assertEqual(chosen, [5])  # 只剩 1 条可用

    def test_prefers_period_tags(self):
        chosen = dh.pick_quotes(self.Q, 2, recent=[], hour=7)  # 晨读：立志/求知/行动/惜时/恒
        tags = {dh.quote_tag(self.Q[i]["text"]) for i in chosen}
        self.assertTrue(tags & {"立志", "求知", "行动", "惜时", "恒"},
                        f"晨读时段应优先偏好主题，实际 {tags}")

    def test_fallback_when_recent_exceeds_pool(self):
        chosen = dh.pick_quotes(self.Q, 3, recent=list(range(6)))
        self.assertTrue(len(chosen) <= 3)

    def test_never_repeats_last(self):
        for _ in range(20):
            chosen = dh.pick_quotes(self.Q, 1, recent=[2])
            self.assertNotIn(2, chosen)


class TestPusher(unittest.TestCase):
    def test_change_detection_dedup(self):
        p = dh.Pusher("http://127.0.0.1:9", dry_run=True)
        payload = {"value": "同一句"}
        self.assertTrue(p.push("k", payload))
        n1 = len(p.dry_log)
        self.assertTrue(p.push("k", payload))  # 内容未变 → 跳过，不追加
        self.assertEqual(len(p.dry_log), n1)
        self.assertTrue(p.push("k", {"value": "变了"}))
        self.assertEqual(len(p.dry_log), n1 + 1)

    def test_force_bypasses_dedup(self):
        p = dh.Pusher("http://127.0.0.1:9", dry_run=True)
        payload = {"value": "心跳"}
        p.push("k", payload)
        n1 = len(p.dry_log)
        p.push("k", payload, force=True)
        self.assertEqual(len(p.dry_log), n1 + 1)

    def test_backoff_growth(self):
        p = dh.Pusher("http://127.0.0.1:9", dry_run=True)
        self.assertEqual(p.backoff(10), 10)
        p.fail_streak = 2
        self.assertEqual(p.backoff(10), 40)
        p.fail_streak = 10
        self.assertEqual(p.backoff(10), 40)  # 封顶 4 倍


class TestDailyRecords(unittest.TestCase):
    def setUp(self):
        self.rec = dh.DailyRecords(_TMP)

    def test_update_and_persist(self):
        self.rec.update(quotes_batches=1)
        rec2 = self.rec.update(quotes_batches=2, habits_shown={"idx": 3, "name": "试"})
        self.assertEqual(rec2["quotes_batches"], 2)
        self.assertEqual(len(rec2["habits_shown"]), 1)
        day = rec2["date"]
        path = Path(_TMP) / "records" / f"{day}.json"
        self.assertTrue(path.exists())
        saved = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(saved["quotes_batches"], 2)

    def test_caps(self):
        for i in range(60):
            self.rec.update(hardware={"level": i})
        rec, _ = self.rec._load(datetime.today().strftime("%Y-%m-%d"))
        self.assertLessEqual(len(rec["hardware"]), dh.DailyRecords.CAPS["hardware"])

    def test_dry_run_no_write(self):
        rec = dh.DailyRecords(_TMP, dry_run=True)
        before = set((Path(_TMP) / "records").glob("*.json"))
        rec.update(quotes_batches=99)
        after = set((Path(_TMP) / "records").glob("*.json"))
        self.assertEqual(before, after)


class TestSingleInstance(unittest.TestCase):
    def test_pid_helpers(self):
        self.assertFalse(dh._pid_alive(0))
        self.assertTrue(dh._pid_alive(os.getpid()))

    def test_acquire_blocks_second(self):
        # 用一个外部活进程模拟「已有实例」
        other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(8)"])
        try:
            with tempfile.TemporaryDirectory() as td:
                pid_path = Path(td) / ".hub_pid"
                pid_path.write_text(str(other.pid), encoding="utf-8")
                self.assertFalse(dh.acquire_single_instance(pid_path))
                # 死进程 pid 应被接管
                pid_path.write_text("99999999", encoding="utf-8")
                self.assertTrue(dh.acquire_single_instance(pid_path))
        finally:
            other.kill()


class TestConfig(unittest.TestCase):
    def test_defaults(self):
        self.assertIn("api", dh.CFG)
        self.assertGreater(dh.CFG["heartbeat"], 0)
        self.assertGreater(dh.CFG["quote"], 0)
        self.assertIn(dh.CFG["display_mode"], ("daily", "demo"))

    def test_interval_demo_override(self):
        hub = dh.Hub(dry_run=True)
        old = dh.CFG["display_mode"]
        dh.CFG["display_mode"] = "demo"
        try:
            self.assertEqual(hub.interval("quote"), 10)
            self.assertEqual(hub.interval("companion"), 30)
        finally:
            dh.CFG["display_mode"] = old
        self.assertGreater(hub.interval("quote"), 10)


class TestCorpus(unittest.TestCase):
    def test_load_real_corpus(self):
        c = dh.Corpus(Path(__file__).resolve().parent.parent if (TESTS_DIR.parent / "quotes.json").exists()
                      else Path(_TMP))
        n = len(c.quotes())
        # 工作区/仓库均有 999 条语料；测试目录为空时允许 0
        self.assertGreaterEqual(n, 0)
        if n:
            self.assertEqual(n, 999)


if __name__ == "__main__":
    unittest.main(verbosity=2)
