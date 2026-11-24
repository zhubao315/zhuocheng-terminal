# 更新日志

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
