# 更新日志

## v1.4.1 (2026-11-24) · 发布资产与品牌统一

- **品牌命名三者统一**：产品「拙诚日课终端 · ZhuoCheng Terminal」/ 仓库 `zhuocheng-terminal` /
  Pages `https://zhubao315.github.io/zhuocheng-terminal/`；README 增补命名与发布规范表
- **GitHub Pages 落地页**：新增 `docs/index.html`（hero 主张 + OFFLINE FIRST · ZERO API KEY 徽标
  + 999/999/12/30 数据带 + 01 产品理念 → 08 文档许可 八章节），部署自 `/docs` 目录
- **Pages 演示页**：`docs/preview.html` 独立适配 Pages 路径（data/ 优先、../data/ 回退、
  file:// 内置样例兜底），`docs/data/` 内嵌完整 999+999 语料，落地页内嵌手机框 iframe 实时演示
- **README 修订**：微习惯 14 → 30 条（与 v1.3 数据同步）、新增 Pages 部署三步说明、目录结构更新

## v1.4.0 (2026-11-24) · 工程稳定版

### 调度中枢 v2（daily_hub.py 全部重写）
- **调度解耦**：心跳 30s / 金句组 180s / 伴读组 600s / 微习惯 3600s / 硬件 120s / 提醒 900s，
  六个独立任务、独立周期，全部 `HEARTBEAT_INTERVAL` 等环境变量可配（docs/06-configuration.md）
- **变更推送**：Pusher 按内容哈希去重，内容未变不重发；断线指数退避（封顶 4×）+ 失败计数
- **时段感知**：晨读推立志/求知、午后推谨言/笃行、傍晚推自省、深夜推恬静/无常（PERIODS 六时段）
- **每日记录**：`records/YYYY-MM-DD.json` 按日独立落盘（金句组/微习惯/提醒/硬件/事件），
  只增不覆盖，与只读语料彻底分离
- **可靠运行**：单实例保护（.hub_pid + 存活检测）、日志轮转（1MB×2）、语料 mtime 缓存
- **CLI**：`--once --dry-run --check --doctor --version --demo --verbose`；
  `--demo` 保留金句 10s/伴读 30s 演示节奏
- ⚠️ 已知缺口：日课打卡勾选状态存于手机端 WebView，Agent 侧无回读接口（审计报告 P1-3），
  每日记录中如实标注 `checklist_note`

### 品读模式 UI（真机验证）
- **金句页**：中枢每 3 分钟推一组 10 句，组内 ‹上句/下句› 自由翻阅、⏸ 暂停轮换，
  徽标显示「组内 X/10」；新组到达时暂停不打扰
- **AI 伴读页**：重构为单屏阅读器——原文/出处/解读/今日一问同屏分层，
  5 条一组手动翻阅、可暂停，自动轮换不再打断阅读
- 总览磁贴文案更新，清理指向已删 home 页的磁贴与 quote-foot 历次部署重影副本

### 运维与质量
- **manage.py**：doctor / status / start / stop / restart / backup / install 一键运维
- **19 个单元测试**（选句去重/时段偏好/变更检测/记录封顶/单实例/配置），不依赖真机
- 审计报告 docs/04-audit-report.md、路线图 docs/05-improvement-roadmap.md、配置指南 docs/06-configuration.md
- SQLite 暂不引入：按日 JSON 每天不足 5KB，保留 V2.0 迁移路径

## v1.3.0 (2026-11-24)

### 专属应用形态
- **页面精简**：移除 PhoneBox 自带的 Home/AI/Work/System/Processes/Shortcuts/Music/Focus/World
  等页面，仅保留拙诚日课六页，总览置顶；应用冷启动默认显示总览
- **应用图标**：换为「拙诚」图标——深墨圆底 #0f1318 + 青色「拙」字 #2dd4bf + 金色打卡点
  #f59e0b；`tools/build_zhuocheng_apk.py` 一键完成改名+换图标
- 图标替换原理（见 `tools/find_icon.py`）：AndroidManifest `android:icon/roundIcon`
  资源 ID → resources.arsc 反查文件路径；自适应图标 BW.xml 前景 ic_launcher_fg
  与 legacy anydpi 配置的 Res_value **原地 4 字节改写**指向 res/J5.png，
  再替换 J5.png（432px 透明字形）与 5 张 tile/通知 PNG 字节
- res/ 目录资源名被混淆（HM.png 等短名），只能按 arsc 反查定位
- 构建链：`build_zhuocheng_apk.py`（改名+图标）→ `sign_apk.py`（v1 签名）
  → 卸载重装 + root 恢复 shared_prefs 免重新配对

## v1.2.0 (2026-11-24)

### 新栏目 · 静坐三省（替代骑行模式）
- 骑行模式退出栏目，槽位复用为「静坐三省」，贴合日课主题：
  - **主敬 · 呼吸引导**：吸 4s → 屏 2s → 呼 6s 圆圈缩放动画，一息 12 秒
  - **静坐 · 体验来复**：一键起坐计时，今日累计分钟存 localStorage 按日重置
  - **三省打卡**：为人谋而不忠乎 / 与朋友交而不信乎 / 传不习乎，触屏勾选每日清零
  - **日课轮读**：十二条全文每 15 秒轮换
- 兼容性：HTML 组件运行在 Chromium 80，`inset` 简写不可用（Chrome 87+），需展开写

### APK 改名 · 拙诚日课
- 启动器名称由 PhoneBox 改为「拙诚日课」：`tools/rebrand_apk.py` 纯 Python
  二进制补丁——AXML 字符串池（UTF-16）重建，替换 AndroidManifest.xml 中的
  字面 "PhoneBox"，无资源重编译；配合 `sign_apk.py` v1 签名
- 覆盖安装签名不一致（签名器每轮新密钥），需卸载重装 + root 恢复
  shared_prefs（pairing.xml）保持配对，页面配置在电脑端 Agent 不受影响

## v1.1.0 (2026-11-24)

### 金句页 · 品读语境
- 下半屏的「电量/亮度」硬件信息移除（用户不关心），替换为两张语境卡片：
  - **主题 · 出处**：中枢按关键词给每句金句标注主题词（空性/无常/拙诚/恒…18 类），
    并按来源判定文献类别（佛家/道家/儒家/明清格言/古典诗词…）
  - **时辰宜事**：按当前时辰推送「卯时晨读宜立志 / 未时日昳宜省身 / 亥时人定宜安歇」
    等七段宜事与小指引；附「今日已品 N 句」品读计数

### 定时中枢 · 提醒体系
- 新增 **日课提醒** 推送（`rike-reminder`）：每 15 分钟轮换一条，日课十二条各配
  「为什么（remind）+ 2 分钟怎么做（how）」，数据见 `data/rike_reminders.json`
- 微习惯库 **14 → 30 条**（`data/microhabits.json`），每条映射日课十二条
- 中枢页增至六行：日课提醒 / 微习惯 / 金句 / 电量 / 环境感知 / 心跳
- 中枢心跳新增：微习惯与日课提醒的进度、下次提醒倒计时

## v1.0.0 (2026-11-24)

首个公开版本。

### 语料
- 金句库扩容至 **999 条**（此前 42 条），43 个来源，零重复，平均 15.8 字
- AI 伴读库扩容至 **999 条**（此前 28 条）：原文 + 解读 + 今日一问 + 关联日课 + 主题标签
- 版权合规：现代著作（人类简史/十分钟冥想/生死疲劳/绿灯/梁永安的爱情课/焦虑的人）仅收录
  项目原创「主题转写」并明确标注，不冒用原文
- `tools/build_corpus.py` 固定种子构建，`tools/validate_corpus.py` 全量校验
  （数量/重复/schema/长度/版权白名单）

### 终端
- 总览页六磁贴一键切换五个阶段
- 金句/伴读长文本自动换行（替换 push 组件的 nowrap+省略号）
- 金句 10 秒随机轮换（不重复）、伴读 30 秒轮换、微习惯 60 分钟轮换、硬件 90 秒采集
- 中枢心跳信息：运行时长 / 今日推送计数 / 连接方式（WiFi adb 或 USB）/ 轮换进度 / 下次采集倒计时
- WiFi adb 断线自动重连，拔掉数据线照常采集
- WebView「版本过旧」黄条去除方案（见 docs/02-phonebox-pitfalls.md）

### 工具
- v1 APK 签名器 `sign_apk.py`（纯 Python，cryptography 实现）
- 脚本全部参数化：`PHONEBOX_API` / `PHONEBOX_ADB` / `PHONEBOX_WIFI_ADB` / `PHONEBOX_DATA_DIR`
