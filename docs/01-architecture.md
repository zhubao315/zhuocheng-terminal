# 01 · 架构说明

## 总体架构

```
┌─────────────────────────┐        ┌──────────────────────────────┐
│  电脑（中枢）             │  adb   │  手机（红米 Note 2）           │
│                         │ ─────→ │  LineageOS 16 + PhoneBox     │
│  daily_hub.py           │  WiFi  │                              │
│  ├─ 每 10s  金句随机      │        │  PhoneBox 面板页面：           │
│  ├─ 每 30s  伴读随机      │  HTTP  │  ├─ overview  总览磁贴         │
│  ├─ 每 60m 微习惯随机     │ ─────→ │  ├─ quote     每日金句         │
│  ├─ 每 90s  硬件采集      │        │  ├─ checkin   日课打卡         │
│  └─ 每 10s  心跳状态      │ 8765   │  ├─ companion AI 伴读          │
│                         │        │  └─ hub       定时中枢         │
│  quotes.json  999 条     │        │                              │
│  companion.json 999 条   │        │  组件：push / checklist / html │
└─────────────────────────┘        └──────────────────────────────┘
```

- **电脑中枢**负责所有「智力」（选条、组稿、采集），手机只负责「显示与触控」——这是刻意的设计：
  旧手机性能弱、Webview 老，复杂逻辑放手机上必然踩坑。
- **推送键约定**：`daily-quote`（金句）、`ai-passage`（伴读原文）、`ai-insight`（伴读解读）、
  `micro-habit`（微习惯）、`hub-info`（心跳）、`phone-batt`（电量）、`phone-sensor`（环境）。
- **HTML 组件桥接**：页面里的 `<script>` 通过 `phonebox.on('push', fn)` 监听推送并更新 DOM，
  大字号金句/伴读原文都用 HTML 组件实现自动换行（push 组件会截断，见踩坑指南）。

## 五阶段演进

| 阶段 | 内容 | 关键文件 |
|---|---|---|
| 1 | 金句库上线（42 条起步） | `push_quote.py` |
| 2 | 日课打卡（触屏双列清单） | `setup_checklist.py` + `rike_items.json` |
| 3 | AI 伴读（预生成解读） | `ai_companion.py` |
| 4 | 定时中枢（心跳+硬件采集） | `daily_hub.py` |
| 5 | 总览页一键切换 + 大字号改版 | `setup_overview.py` |
| 6 | 语料扩容至 999+999 + 开源产品化 | `tools/build_corpus.py` |

## 中枢心跳节奏

```
10 秒     金句随机（不与上一条重复） + hub-info 心跳
30 秒     伴读随机（ai_companion.choose_index 避免连续重复）
60 分钟   微习惯随机（跨日重置）
90 秒     硬件采集（电量/温度/光线/屏幕状态；设备离线时自动尝试 WiFi adb 重连）
```

轮换进度与运行状态都会写进 `hub-info` 推送，在「定时中枢」页可见，形成「活着的仪表盘」。

## 语料构建管线

```
corpus_sources/*.py      # 公版摘句 + 原创金句 + 主题转写
        │  (build_corpus.py)
        ├─ 去重（按去除空白后的全文本）
        ├─ 自动打标签（关键词规则，19 个标签）
        ├─ 裁剪到 999（优先级：公版典籍 > 原创转写）
        └─ 生成伴读（固定种子）：直解 + 拙诚桥接 + 落地动作 + 思考题 + 关联日课
        ↓
data/quotes.json + data/companion.json
        ↓ (validate_corpus.py)
数量/重复/schema/长度/版权白名单 全部通过
```

设计取舍：解读用「主题族语池」组合而非逐条手写，是为了在离线、无 API key 的约束下
把语料规模做到 999 条；固定随机种子保证任何人重建出的语料完全一致（可审计）。
