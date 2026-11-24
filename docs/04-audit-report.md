# 04 · 审计报告（Audit Report）

> 生成日期：2026-11-24 · 审计对象：拙诚日课终端 v1.3.0 → v2.0.0 中枢
> 原则：以真实代码为准，未经真机验证的功能一律标注「尚未验证」。

## 1. 当前架构

```
┌─────────────────────────── 电脑端（全部核心逻辑） ───────────────────────────┐
│                                                                              │
│  daily_hub.py v2（智能调度中枢）                                              │
│  ├─ Heartbeat    心跳        30s      ├─ Quote Rotation   金句组    180s     │
│  ├─ Companion    伴读组      600s     ├─ Microhabit       微习惯    3600s    │
│  ├─ Hardware     硬件采集     120s    ├─ Reminder         日课提醒  900s    │
│  └─ Pusher（内容哈希·只推变化）  DailyRecords（records/YYYY-MM-DD.json）     │
│                                                                              │
│  Corpus（quotes 999 / companion 999 / microhabits 30 / reminders 12）        │
│  语料只读缓存（mtime 感知，不重复加载）                                       │
│                                                                              │
│  PhoneBox Adapter：POST /api/push/<key> · GET/PUT /api/settings              │
│                    POST /api/goto/<page> · GET /api/state                    │
└──────────────────────────────────┬───────────────────────────────────────────┘
                    USB / WiFi adb（192.168.1.66:5555）+ 本地 HTTP
┌──────────────────────────────────┴───────────────────────────────────────────┐
│  红米 Note 2 (hermes) · LineageOS 16 · WebView Chromium 80                   │
│  PhoneBox 桌面面板（改名「拙诚日课」APK）                                      │
│  页面：总览 / 金句(品读模式) / 日课打卡 / AI伴读(单屏阅读器) / 静坐三省 / 中枢  │
└──────────────────────────────────────────────────────────────────────────────┘
```

## 2. 功能与数据清单

| 资产 | 规模 | 状态 |
|---|---|---|
| 金句库 quotes.json | 999 条 · 43 来源 | ✅ 校验通过（validate_corpus.py） |
| 伴读库 companion.json | 999 条（原文+解读+一问+日课+标签） | ✅ |
| 微习惯 microhabits.json | 30 条 · 映射日课十二条 | ✅ |
| 日课提醒 rike_reminders.json | 12 条 | ✅ |
| 日课十二条 rike_items.json | 12 条（名称/原文未改动） | ✅ |
| 每日记录 records/ | 每天一个 JSON，只增不覆盖 | ✅ v2 新增 |
| 测试 tests/ | 19 个用例，全部通过 | ✅ v2 新增 |

## 3. 审计发现的问题与整改状态

| 编号 | 优先级 | 问题 | 状态 |
|---|---|---|---|
| P0-1 | 高 | 心跳/内容/硬件绑在同一个 10 秒循环，每拍全量加载语料+推送全部组件 | ✅ v2 解耦为 6 个独立任务 |
| P0-2 | 高 | 金句 10 秒强制轮换，床头阅读体验差 | ✅ 改为 3 分钟一组（10 句）+ 页面暂停/翻页；10s 保留为 `--demo` 模式 |
| P0-3 | 高 | 伴读 30 秒自动换，长文读不完 | ✅ 改为 10 分钟一组（5 条）+ 暂停/翻页，不打断阅读 |
| P0-4 | 高 | 无日课历史：每日重置即丢失，语料和个人数据未分离 | ✅ records/ 按日独立落盘（金句组/微习惯/提醒/硬件/事件） |
| P0-5 | 高 | 无变更检测，断线时每 10 秒无效重试 | ✅ Pusher 内容哈希 + 指数退避（封顶 4×） |
| P1-1 | 中 | 语料每拍重新 json.loads | ✅ Corpus mtime 缓存 |
| P1-2 | 中 | 无单实例保护，可重复启动多个中枢 | ✅ .hub_pid + 进程存活检测 |
| P1-3 | 中 | **打卡勾选状态存于手机端 WebView，Agent 侧无回读接口**（/api/state 与 settings 均不含 checked 字段） | ⚠️ 未解决——上游接口未提供，每日记录中如实标注 `checklist_note`；待 PhoneBox 上游支持后接入 |
| P1-4 | 中 | hub.log 无轮转 | ✅ RotatingFileHandler 1MB×2 |
| P1-5 | 中 | 无 CLI 诊断 | ✅ --once/--dry-run/--check/--doctor/--version/--demo/--verbose + manage.py |
| P2-1 | 低 | 时段感知（早晨立志/深夜恬静） | ✅ PERIODS 六时段偏好主题池 |
| P2-2 | 低 | 总览页残留指向已删除 home 页的磁贴 | ✅ 已清理 |
| P2-3 | 低 | quote-foot 组件历次部署堆积副本（重影隐患） | ✅ 去重改为清理全部 `quote*` 前缀 |

## 4. 数据风险

1. **打卡历史不可回读**（P1-3）是当前最大数据缺口；缓解：中枢记录的每日记录完整保留「终端交付了什么」，行为侧数据待上游。
2. `.hub_state.json` 为运行状态（可丢弃），个人数据只在 records/ 与 backups/ —— 已通过 manage.py backup 打包。
3. 语料为只读资产，重新构建（build_corpus.py 固定种子）不会触碰 records/。

## 5. 版权边界（维持 v1.0 声明）

- 公版古籍摘句：public_domain
- 项目原创：project_original（拙诚原创 214 条）
- 现代书主题转写（冥想/简史/疲劳/绿灯/爱情课/焦虑的人）：**精神转写并明确标注，不复制原文**，共 37 条，rights_status=needs_review（发布前建议逐条复核）
- 飞鸟集采用郑振铎公版译本

## 6. 结论

不需要数据库服务器/Redis/Docker；SQLite 暂不引入——按日 JSON 文件已满足当前数据规模（每天 < 5KB），保留升级路径（见 05 路线图 V2.0）。运行时零 API Key、零互联网依赖的原则全程成立。
