# 06 · 配置指南（Configuration）

优先级：**命令行参数 > 环境变量 > 默认值**。所有路径不硬编码，可移植部署。

## 环境变量

| 变量 | 默认 | 说明 |
|---|---|---|
| `PHONEBOX_API` | `http://127.0.0.1:8765` | PhoneBox Agent 本地 API |
| `PHONEBOX_ADB` | `<工作区>/flash-hermes/platform-tools/adb.exe` | adb 可执行文件路径 |
| `PHONEBOX_WIFI_ADB` | `192.168.1.66:5555` | WiFi adb 地址（拔线采集） |
| `PHONEBOX_DATA_DIR` | 脚本所在目录 | 语料/状态/记录目录 |
| `HEARTBEAT_INTERVAL` | `30` | 心跳周期（秒） |
| `QUOTE_INTERVAL` | `180` | 金句组轮换（秒，每组 10 句） |
| `COMPANION_INTERVAL` | `600` | 伴读组轮换（秒，每组 5 条） |
| `MICROHABIT_INTERVAL` | `3600` | 微习惯轮换（秒） |
| `HARDWARE_INTERVAL` | `120` | 硬件采集（秒） |
| `REMINDER_INTERVAL` | `900` | 日课提醒轮换（秒） |
| `DISPLAY_MODE` | `daily` | `daily` 日常 / `demo` 演示（金句 10s、伴读 30s） |
| `LOG_LEVEL` | `INFO` | 日志级别 |

## 命令行

```bash
python daily_hub.py --once        # 推一轮
python daily_hub.py --dry-run     # 只算不推不落盘
python daily_hub.py --check       # 快速体检
python daily_hub.py --doctor      # 完整诊断
python daily_hub.py --demo        # 演示节奏
python scripts/manage.py doctor | status | start | stop | restart | backup | install
python -m unittest discover tests -v   # 单元测试
```

## 节奏示例

```bash
# 床头慢节奏：金句组 10 分钟一换
QUOTE_INTERVAL=600 python daily_hub.py
# 演示给别人看
python daily_hub.py --demo
```
