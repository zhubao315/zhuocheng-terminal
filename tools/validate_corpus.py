# -*- coding: utf-8 -*-
"""拙诚日课终端 · 语料校验器

校验 data/quotes.json 与 data/companion.json：
  1. 数量 = 999
  2. 金句文本零重复
  3. schema 完整（quotes: text/source/tag；companion: passage/source/insight/question/practice/tag）
  4. 金句与伴读原文一一对应
  5. 长度分布（最长不超过 60 字，避免面板两行放不下）
  6. practice 均为日课十二条合法值
  7. 版权合规：非公版来源必须标注「拙诚日课 · 原创/转写」

用法: python tools/validate_corpus.py
"""
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"

VALID_PRACTICES = {"主敬", "静坐", "早起", "读书不二", "读史", "谨言", "养气",
                   "保身", "日知所亡", "月无忘所能", "作字", "夜不出门", "日课十二条"}

errors, warns = [], []


def main():
    quotes = json.loads((DATA / "quotes.json").read_text(encoding="utf-8"))
    companions = json.loads((DATA / "companion.json").read_text(encoding="utf-8"))
    qi, ci = quotes["items"], companions["items"]

    def chk(cond, msg):
        (errors if not cond else []).append(msg) if not cond else None

    if len(qi) != 999:
        errors.append(f"金句数量 {len(qi)} ≠ 999")
    if len(ci) != 999:
        errors.append(f"伴读数量 {len(ci)} ≠ 999")

    keys = [q["text"].replace(" ", "") for q in qi]
    dups = [k for k, v in Counter(keys).items() if v > 1]
    if dups:
        errors.append(f"金句重复 {len(dups)} 条: {dups[:3]}")

    for i, q in enumerate(qi):
        if not q.get("text") or not q.get("source") or not q.get("tag"):
            errors.append(f"金句[{i}] schema 缺字段")
        if len(q["text"]) > 60:
            warns.append(f"金句[{i}] 过长 {len(q['text'])} 字: {q['text'][:20]}…")

    for i, c in enumerate(ci):
        for k in ("passage", "source", "insight", "question", "practice", "tag"):
            if not c.get(k):
                errors.append(f"伴读[{i}] 缺 {k}")
        if c.get("practice") not in VALID_PRACTICES:
            errors.append(f"伴读[{i}] practice 非法: {c['practice']}")
        if len(c.get("insight", "")) < 40:
            warns.append(f"伴读[{i}] 解读过短")

    qtexts = {q["text"] for q in qi}
    mismatch = [i for i, c in enumerate(ci) if c["passage"] not in qtexts]
    if mismatch:
        errors.append(f"伴读原文与金句不对应 {len(mismatch)} 条: {mismatch[:5]}")

    # 版权合规：来源必须含「拙诚日课 ·」前缀（原创/转写）或为公版典籍白名单
    PUBLIC = {"金刚经", "龙树《中论》", "《六祖坛经》", "《八大人觉经》", "老子《道德经》",
              "庄子", "孔子《论语》", "孟子", "《大学》", "《中庸》", "《朱子家训》",
              "泰戈尔《飞鸟集》", "《诗经》", "《古诗十九首》", "苏轼", "陶渊明", "王维",
              "李白", "杜甫", "刘禹锡", "李清照", "辛弃疾", "陆游", "王安石",
              "王阳明《传习录》", "《周易》", "荀子", "《孙子兵法》", "《史记》",
              "曾国藩", "《了凡四训》", "《菜根谭》", "《小窗幽记》", "《围炉夜话》",
              "吕坤《呻吟语》", "《增广贤文》", "拙诚日课 · 原创"}
    bad_src = [q["source"] for q in qi
               if q["source"] not in PUBLIC and not q["source"].startswith("拙诚日课 · ")]
    if bad_src:
        errors.append(f"来源不在白名单: {set(bad_src)}")

    lens = [len(q["text"]) for q in qi]
    print(f"金句 999 ✓" if len(qi) == 999 else f"金句 {len(qi)} ✗")
    print(f"伴读 999 ✓" if len(ci) == 999 else f"伴读 {len(ci)} ✗")
    print(f"文本重复: {len(dups)} · 最长 {max(lens)} 字 · 平均 {sum(lens)/len(lens):.1f}")
    print(f"来源数: {len({q['source'] for q in qi})} · 标签数: {len({q['tag'] for q in qi})}")
    print(f"warnings: {len(warns)} · errors: {len(errors)}")
    for w in warns[:10]:
        print("  ⚠", w)
    for e in errors[:10]:
        print("  ✗", e)
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
