# 全离线版 2.0 · ZhuoCheng Terminal Offline

> 一句话：**把内容引擎从电脑搬进手机**。不配对、不联网、不启动电脑端，打开 APK 就是完整的拙诚日课终端。

## 1. 为什么要做这一版

v1.4.4 只是把 PhoneBox 外壳的「电脑未连接 / 点击唤醒 / 等待推送」提示隐藏了，但金句和伴读仍然由电脑上的 `daily_hub.py` 通过 PhoneBox 本地 API 推送。拔掉电脑后，墙上那块屏幕只能停在空状态——这不是「全离线」。

全离线版 2.0 修正了这个回退：

| 对比项 | 桥接版 v1.4.4 | 全离线版 2.0 |
|---|---|---|
| 内容轮换 | 电脑 Python 中枢推送 | 手机 WebView 本地定时器 |
| 电脑端 | 必须常驻 PhoneBoxAgent + daily_hub | **完全不需要** |
| 网络 | 局域网 API | **不需要** |
| 金句 / 伴读 | 推送到 widget | 999 + 999 条全部内嵌 |
| 日课 / 微习惯勾选 | 存手机配置，电脑无法回读 | 按日期存本机 `localStorage`，可回看历史 |
| 静坐 / 省身 / 收藏 | 无 | 本地记录，可导出 Markdown / JSON |
| 离线浮层 | 用 CSS 隐藏 | 外壳被离线应用整体替代，根本不加载 |
| 硬件采集（电量/温度/光） | 电脑 adb 采集 | 不提供（没有电脑就没有采集源，不造假数据） |

## 2. 运行方式

- **APK**：`releases/zhuocheng-offline-2.0.apk`，安装后直接打开。
- **免安装**：手机浏览器打开 Pages 上的 [`offline.html`](offline.html)，功能一致。
- **桌面浏览器**：同样可用，便于调试；数据存在该浏览器本地。

## 3. 页面与交互

七个页签（底部导航，大触控区）：

1. **总览**：日期、今日主题、大字金句、日课进度、当前微习惯、本地引擎状态与轮换倒计时。
2. **每日金句**：999 条内置金句；每 180 秒自动换新；上一条 / 暂停 / 下一条 / 收藏 / A−A＋ 字号调节。
3. **AI 伴读**：999 条「原文 + 品读 + 今日一问 + 关联日课」；每 600 秒自动换新；一键跳到静坐。
4. **日课十二条**：双列大按钮；按日期勾选；可翻看历史日期、清空当日；进度条实时更新。
5. **微习惯**：30 条；每小时轮换；完成 / 稍后 / 跳过三态记录；可手动换一条或暂停。
6. **静坐三省**：5/10/15/20 分钟计时与呼吸引导；三省勾选；省身笔记；保存到档案。
7. **成长档案**：有记录天数、连续天数、微习惯完成、静坐次数/分钟、近 7 日日课条、收藏列表，以及 Markdown / JSON 导出。

日间/夜间主题可在右上角切换；字号在金句页调节。所有设置与记录跟随本机。

## 4. 技术实现

- 单文件应用：`docs/offline.html`（约 573 KB），内联数据、CSS、JS，无任何外链字体、图片、CDN。
- 源码：`web/offline/app.html` / `app.css` / `app.js`；由 `tools/build_offline_bundle.py` 从 `data/*.json` 构建。
- 数据：`localStorage['zhuocheng.offline.v2']`，按日期保存 `rike` / `habits` / `sits` / `notes`，另有收藏、主题、字号与索引；历史日期只增不覆盖。
- 轮换计时器在页面内运行，暂停状态持久化；刷新或重开应用后从当前索引继续，不会因为「离线太久」立即连跳。
- APK：`tools/build_offline_apk.py` 只替换 PhoneBox 基座的 `assets/www/index.html`，沿用原包名与图标；`scripts/sign_apk_v2.py` 做 v1+v2 双签，与旧版同一签名身份，可覆盖安装。

复现构建：

```bash
python tools/build_offline_bundle.py
python tools/build_offline_apk.py releases/zhuocheng-terminal-v2signed.apk releases/zhuocheng-offline-2.0-unsigned.apk
python scripts/sign_apk_v2.py releases/zhuocheng-offline-2.0-unsigned.apk releases/zhuocheng-offline-2.0.apk
python scripts/sign_apk_v2.py --verify releases/zhuocheng-offline-2.0.apk
```

浏览器冒烟测试：`node promotion/offline_qa.mjs`；真机截图脚本：`node promotion/offline_device_shots.mjs`（需无线 adb 与 WebView 调试通道）。

## 5. 真机验证（2026-11-25）

- 设备：红米 Note 2 / LineageOS 16 / Android 9 / 无线 adb `192.168.1.66:5555`。
- `adb install -r` 成功；打开后直接显示内置金句「应无所住而生其心。」，无「电脑未连接」「点击唤醒」「等待推送」。
- 通过 WebView CDP 逐页验证：金句上下条、伴读原文与今日一问、日课 12 条勾选进度、微习惯完成计数、静坐计时、档案统计与本地存储均正常；控制台无异常。
- 七张真机截图见 `docs/screens/`。

## 6. 已知边界

- 全离线模式不采集硬件传感器数据（那是电脑端桥接版的能力）；界面只展示可靠的本地状态。
- 浏览器 `file://` 打开时，个别浏览器可能限制 localStorage；Pages 的 https 页面与 APK WebView 均已验证可用。
- 导出使用浏览器下载 / 文本框复制；在部分定制 WebView 中若下载被拦截，导出的文本仍会显示在页面文本框中，可长按复制。
- 深层主题阅读、SQLite 迁移与年度总结仍按 `docs/05-improvement-roadmap.md` 的 V2.0 路线推进，不属于本次「全离线 2.0」范围。
