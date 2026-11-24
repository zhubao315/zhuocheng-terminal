# 拙诚日课终端 · ZhuoCheng Terminal

> 把一台 2015 年的旧安卓手机，改造成床头「日课修行终端」：
> 每日金句 10 秒轮换 · AI 伴读 30 秒轮换 · 曾国藩日课十二条触屏打卡 · 微习惯每小时轮换 · 硬件感知中枢。
>
> 硬件原型：红米 Note 2（hermes / MT6795，刷入 LineageOS 16）+ [PhoneBox](https://ersinkoc.github.io/phonebox/) 面板。
> 无需任何 API key、无需联网抓取——全部 999 条伴读解读在构建期预生成。

![status](https://img.shields.io/badge/quotes-999-blue) ![status](https://img.shields.io/badge/companions-999-purple) ![license](https://img.shields.io/badge/code%20license-MIT-green)

## 它是什么

拙诚日课终端把一部退役手机变成一张「常亮的修行桌面」：

| 模块 | 节奏 | 内容 |
|---|---|---|
| 每日金句 | 每 10 秒随机换（不与上一条重复） | 999 条金句，43 个来源 |
| AI 伴读 | 每 30 秒随机换 | 999 条自包含条目：原文 + 解读 + 今日一问 + 关联日课 |
| 日课打卡 | 触屏勾选，每日自动重置 | 曾国藩日课十二条，双列清单 |
| 微习惯 | 每小时随机换 | 14 条 2 分钟可完成的微习惯，映射日课 |
| 定时中枢 | 10 秒心跳 | 运行时长/推送计数/连接方式/轮换进度/下次采集倒计时 + 电量、环境光等硬件采集 |

设计哲学来自「拙诚」：**结硬寨，打呆仗**——用笨功夫把一套系统搭起来，然后等待复利。

## 成品一览

跑在手机上的面板（PhoneBox）：

```
┌────────────────────────────────────┐
│  总览（六个入口磁贴，一键切换）        │
├────────────────────────────────────┤
│  ┌──────────────┐ ┌──────────────┐ │
│  │  每日金句     │ │  定时中枢     │ │
│  │  （10 秒轮换）│ │  （10 秒心跳）│ │
│  └──────────────┘ └──────────────┘ │
│  ┌──────────────┐ ┌──────────────┐ │
│  │  AI 伴读     │ │  日课打卡     │ │
│  │  （30 秒轮换）│ │  （两列清单） │ │
│  └──────────────┘ └──────────────┘ │
│  ┌────────────────────────────────┐│
│  │  今日微习惯（每小时轮换）          ││
│  └────────────────────────────────┘│
└────────────────────────────────────┘
```

浏览器打开 [`web/preview.html`](web/preview.html) 可以直接体验金句/伴读轮换效果（无需手机）。

## 快速开始

### 0. 准备

- 一台安卓手机（Android 5+ 即可，旧手机最佳），安装 [PhoneBox](https://ersinkoc.github.io/phonebox/) 并与本机配对
- 电脑安装 Python 3.8+、adb（加入 PATH，或用 `PHONEBOX_ADB` 指定路径）

### 1. 部署面板页面

```bash
cd scripts
python setup_checklist.py     # 日课打卡页（两列清单）
python ai_companion.py --setup  # AI 伴读页
python setup_overview.py      # 总览页 + 各页组件（一键部署）
```

### 2. 启动中枢

```bash
python daily_hub.py           # 常驻心跳（默认）
python daily_hub.py once      # 推一轮（测试）
```

中枢会自动把金句/伴读/微习惯/硬件状态推送到面板，并每 10 秒写入心跳。

### 3. 可选环境变量

| 变量 | 默认值 | 说明 |
|---|---|---|
| `PHONEBOX_API` | `http://127.0.0.1:8765` | PhoneBox 本地 API 地址 |
| `PHONEBOX_ADB` | `adb` | adb 可执行文件路径 |
| `PHONEBOX_WIFI_ADB` | `192.168.1.66:5555` | WiFi adb 地址（拔线采集） |
| `PHONEBOX_DATA_DIR` | `../data` | 语料 JSON 所在目录 |

## 语料库（本项目最有价值的部分）

- [`data/quotes.json`](data/quotes.json) — **999 条金句**，43 个来源，文本零重复，平均 15.8 字
- [`data/companion.json`](data/companion.json) — **999 条 AI 伴读**（原文 + 解读 + 思考题 + 关联日课 + 主题标签）
- [`data/microhabits.json`](data/microhabits.json) — 14 条微习惯
- [`data/rike_items.json`](data/rike_items.json) — 日课十二条清单

### 来源分布（TOP）

| 来源 | 条数 | 版权 |
|---|---|---|
| 拙诚日课 · 原创 | 220 | 本项目原创，随仓库许可发布 |
| 老子《道德经》 | 88 | 公版 |
| 孔子《论语》 | 82 | 公版 |
| 《金刚经》 | 63 | 公版 |
| 曾国藩 | 57 | 公版（卒于 1872） |
| 《增广贤文》/《飞鸟集》/《菜根谭》/《传习录》… | … | 公版 |

### 版权与合规声明

1. **公版经典**：金刚经、中论、坛经、道德经、论语、孟子、庄子、菜根谭、增广贤文、曾国藩家书等均在公有领域，摘句保留原文。
2. **现代著作只做「主题转写」**：《十分钟冥想》《人类简史》《生死疲劳》《绿灯》《梁永安的爱情课》《焦虑的人》受版权保护，本项目**不收录原文引文**，只收录标注为「拙诚日课 · XX转写」的项目原创表述，仅承其精神。
3. **解读/思考题**：全部由 `tools/build_corpus.py` 按主题族语池预生成（随机种子固定，构建可复现），为本项目原创内容。
4. 校验脚本 `tools/validate_corpus.py` 内置来源白名单，防止版权不合规条目混入。

### 自定义语料

```bash
# 编辑 corpus_sources/ 下任一模块，或新建模块并在 build_corpus.py 中注册
python tools/build_corpus.py          # 重建 999 + 999
python tools/validate_corpus.py       # 全量校验（数量/重复/schema/版权白名单）
```

## 目录结构

```
zhuocheng-terminal/
├── data/                  # 999 金句 + 999 伴读 + 微习惯 + 日课清单
├── scripts/               # 运行时脚本（部署面板页面 + 定时中枢）
│   ├── daily_hub.py       # 10 秒心跳中枢
│   ├── ai_companion.py    # 伴读推送
│   ├── setup_overview.py  # 总览页一键部署
│   ├── setup_checklist.py # 日课打卡页
│   ├── push_quote.py      # 手动推一条金句
│   └── sign_apk.py        # v1 APK 签名器（改 WebView 黄条后重打包用）
├── tools/                 # 语料构建与校验
│   ├── build_corpus.py    # 999+999 构建器（固定种子，可复现）
│   ├── validate_corpus.py # 全量校验器
│   └── portable_patch.py  # 脚本可移植化补丁（开发用）
├── corpus_sources/        # 公版摘句源文件 + 原创金句池
├── docs/                  # 架构说明 / PhoneBox 踩坑指南 / 安装指南
└── web/preview.html       # 浏览器演示页
```

## 文档

- [docs/01-architecture.md](docs/01-architecture.md) — 五阶段架构与推送键约定
- [docs/02-phonebox-pitfalls.md](docs/02-phonebox-pitfalls.md) — **PhoneBox 踩坑指南（血泪经验）**：HTML 组件独立 iframe 渲染、重复 id 重影、长文本截断、切页温柔切换、WebView 黄条去除、APK 重签名……
- [docs/03-install.md](docs/03-install.md) — 旧手机刷机与部署指南

## 常见问题

**Q: 必须是红米 Note 2 吗？**
不是。任何能跑 Android 5+ 并安装 PhoneBox 的设备都可以；旧平板、旧手机都合适。

**Q: 伴读是 AI 实时生成的吗？**
不是。为保证离线可用与响应即时，解读在构建期由语池预生成；中枢只做随机轮换推送。

**Q: 想换成自己的书单？**
编辑 `corpus_sources/` 里的模块或新建模块，重跑构建器即可。保持来源标注真实——这是本项目的底线。

## 许可

- 代码：[MIT License](LICENSE)
- 数据：公版原文进入公有领域；「拙诚日课 · 原创 / 转写」条目与解读以 MIT 同步发布
- 请保留来源标注，勿将转写条目冒充原书引文

## 致谢

- [PhoneBox](https://ersinkoc.github.io/phonebox/) by Ersin Koç — 让旧手机变成信息面板的出色项目
- 曾国藩、泰戈尔、龙树、老子，以及所有先贤——他们才是真正的作者
