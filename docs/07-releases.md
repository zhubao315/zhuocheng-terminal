# 07 · 发布与校验（Releases）

## 当前正式产物

| 项目 | 值 |
|---|---|
| 版本 | v1.4.2（中枢 v2.0.0；PhoneBox 基座 0.9.29） |
| 文件 | `releases/zhuocheng-terminal-v2signed.apk`（Pages 镜像：`docs/releases/`） |
| 大小 | **2,360,405 字节** |
| SHA-256 | `fade370b9f5946aeb39c8afd6381e81bea771f3174b121c3b742637e03dc94f6` |
| 签名 | v1（JAR）+ v2（APK Signature Scheme v2），同一密钥 |
| 证书 SHA-256 指纹 | `fe7a86a5e0a3b7776fbcbedd6595d879f33a999a4fcf10154639eadc5f90e5be` |
| 包名 | `net.oxog.phonebox.deskpanel` |
| minSdk / targetSdk | 21（Android 5.0+） / 35（Android 15） |
| 架构 | 无 native 库，CPU 架构中立（32/64 位均可） |
| 构建来源 | PhoneBox 0.9.29 基座 + 拙诚品牌二进制补丁；`scripts/sign_apk_v2.py` 签名 |

## 下载与校验

```bash
# Pages 直链
curl -O https://zhubao315.github.io/zhuocheng-terminal/releases/zhuocheng-terminal-v2signed.apk
# 或用仓库原始文件
curl -O https://raw.githubusercontent.com/zhubao315/zhuocheng-terminal/main/releases/zhuocheng-terminal-v2signed.apk

sha256sum zhuocheng-terminal-v2signed.apk
# 应输出 fade370b9f5946aeb39c8afd6381e81bea771f3174b121c3b742637e03dc94f6

# 签名指纹（需本机已有 .keys/；签名器 --fingerprint 会拒绝身份不完整）
python scripts/sign_apk_v2.py --fingerprint
python scripts/sign_apk_v2.py --verify <apk>     # 结构 + 摘要 + RSA 验签自校验
```

## 已验证 / 未验证的兼容范围

- ✅ **Android 9**（红米 Note 2 / LineageOS 16）：真机安装成功、面板正常显示
- ✅ **Android 11+ 签名要求**：v2 签名链路真机验证通过（摘要 / RSA / 证书解析均通过）
- ⚠️ **Xiaomi HyperOS 3.0（Redmi K70）**：系统安装器曾以 `-124` 拒绝侧载，与 APK 架构无关（包内无 native 库）；请关闭纯净模式后用系统文件管理器安装，或开启 USB 调试 + USB 安装后用 `adb install -r` 直装。**尚未完成真机成功安装验证**。
- ⚠️ 其他 Android 版本 / 品牌定制系统：尚未逐一验证

## 升级与密钥

- `.keys/`（私钥 + 自签证书）不入库，需 offline 加密备份；**只丢一个文件时签名器会报错退出，绝不自动生成新身份**（否则旧版本无法覆盖升级）。
- 旧手机若装的是早期仅 v1 签名的版本，升级到本包前需先卸载旧版（签名身份不同）。
- 发布新包前必须更新本文件的 SHA-256、指纹与变更记录。

## 变更记录

- v1.4.2：新增纯 Python v2 签名器，修复 Android 11+ 安装报错 33
- v1.4.1：Pages 落地页、演示页、品牌命名统一
- v1.4.0：中枢 v2（六任务解耦、每日记录、CLI、19 项测试）
