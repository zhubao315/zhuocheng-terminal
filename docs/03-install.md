# 03 · 安装指南

从一台退役旧手机到床头日课终端的完整路径。

## A. 硬件与系统

- 推荐机型：2015–2019 年的安卓手机/平板（原型：红米 Note 2 / hermes）
- 系统：Android 5–9 均可（原型为 LineageOS 16 / Android 9）
- 电池：长期插电使用请留意鼓包风险，建议放在通风处、套绝缘壳

> 刷机方法超出本文范围。红米 Note 2 可参考小米社区/LineageOS 官方 wiki 的 hermes 章节；
> 刷机有风险，请自行承担并做好备份。

## B. 基础设置

```bash
# 1. 常亮（床头终端必备）
adb shell settings put system screen_off_timeout 2147483647

# 2. WiFi adb（拔线采集）
adb shell setprop persist.adb.tcp.port 5555
adb tcpip 5555
adb connect <手机IP>:5555

# 3. 校时（老机型时间容易漂）
adb shell settings put global auto_time 1
```

## C. 安装 PhoneBox

1. 下载 [PhoneBox APK](https://ersinkoc.github.io/phonebox/)，安装并配对电脑端。
2. 确认本地 API 可访问：`http://127.0.0.1:8765/api/settings`。
3. （可选）去除「WebView 版本过旧」黄条：解包 APK → 修改 `index.html` 中 WebView
   检测逻辑 → `python scripts/sign_apk.py` 重签名 → 安装。
   **不要**直接改已安装 APK 的内容再放回（会被包管理器校验移除）。

## D. 部署本项目

```bash
git clone <本仓库> && cd zhuocheng-terminal/scripts

# 部署面板页面（每步之间 PhoneBox 有 15 秒温柔切换保护，脚本已内置等待）
python setup_checklist.py
python ai_companion.py --setup
python setup_overview.py

# 启动中枢
python daily_hub.py
```

看到 `中枢心跳` 推送出现「已运行 0m00s」即部署成功。

## E. Termux 进阶（可选）

在手机上装 Termux 后，可以把中枢直接跑在手机本机（`PHONEBOX_API` 仍指向 127.0.0.1:8765），
彻底摆脱电脑。注意 Android 9 的 Termux 源已停止更新，建议使用旧版安装包。

## F. 验证清单

- [ ] 总览页六格磁贴，点击能切页
- [ ] 金句页大字号、长句自动换行、无省略号、无重影
- [ ] 日课页两列十二条，触屏可勾选，勾选后出现绿勾删除线
- [ ] 伴读页原文/解读完整显示
- [ ] 中枢页心跳每 10 秒更新，WiFi adb 显示连接方式
- [ ] 拔掉数据线 5 分钟后，中枢仍在推送
