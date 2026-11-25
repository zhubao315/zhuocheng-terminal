# 07 · 发布与校验（Releases）

## 当前正式产物（全离线版 2.1）

| 项目 | 值 |
|---|---|
| 版本 | v2.1.2 · 全离线版 2.1 信息屏（PhoneBox 基座 0.9.29，仅承载 WebView） |
| 文件 | `releases/zhuocheng-offline-2.0.apk`（Pages 镜像：`docs/releases/`） |
| 大小 | **2,454,841 字节** |
| SHA-256 | `29f539b64821477f7d93031a770c8183fc8d5a797bcc96639996857dac07c8ec` |
| 签名 | v1（JAR）+ v2（APK Signature Scheme v2），同一密钥 |
| 证书 SHA-256 指纹 | `fe7a86a5e0a3b7776fbcbedd6595d879f33a999a4fcf10154639eadc5f90e5be` |
| 包名 | `net.oxog.phonebox.deskpanel` |
| minSdk / targetSdk | 21（Android 5.0+） / 35（Android 15） |
| 架构 | 无 native 库，CPU 架构中立（32/64 位均可） |
| 构建来源 | PhoneBox 0.9.29 基座 + 拙诚品牌二进制补丁；`tools/build_offline_bundle.py` 构建单文件离线应用；`tools/build_offline_apk.py` 替换 WebView 入口；`scripts/sign_apk_v2.py` 双签 |
| v2.1.2 变更 | 信息屏金句 20 秒 / 伴读 40 秒定时换新（可配置，0 关），栏目仍手动切换；默认字号 1.45 → 1.3（约小两号），旧值自动迁移；信息屏禁用文字选择，长按不再弹「复制/分享/全选」；矮屏成长档案标题与末行不再被裁；七张真机截图按 v2.1.2 重取；与旧版同一签名，可直接覆盖安装 |
| v2.1.1 变更 | 修复配置面板关不掉：`[hidden]{display:none !important}` 让 `hidden` 属性始终生效（此前 `.cfg-panel{display:flex}` 覆盖了 UA 默认隐藏规则，抽屉常驻无法关闭）；真机验证冷启动直进金句屏、长按开配置/点关闭正常；与旧版同一签名，可直接覆盖安装 |
| v2.1.0 变更 | 顶部改显「拙诚日课」品牌名并去掉进度条；取消自动轮播，默认静态停在金句；六栏目手动左右切换（滑动 / 点左右半区 / 点栏目名 / 方向键）；配置新增「默认栏目」，「轮播模块」改为「显示栏目」；配置抽屉改为内容独立滚动，矮屏一屏可见；与旧版同一签名，可直接覆盖安装 |
| v2.0.1 变更 | 默认改为全屏信息屏：取消顶部品牌栏与底部七项导航，六模块自动轮播（每屏 20 秒），新增多端配置；矮屏下十二课完整可见 |
| v2.0.0 变更 | 内容引擎搬到手机：999 金句 + 999 伴读 + 日课 + 微习惯 + 静坐 + 成长档案全部内置，零电脑 / 零网络 / 零 API Key；彻底不加载 PhoneBox 离线外壳，无需再隐藏浮层 |

### 可选：桥接版 v1.4.4

仍需电脑端 PhoneBoxAgent + `daily_hub.py` 推送，文件 `releases/zhuocheng-terminal-v2signed.apk`，2,360,718 字节，SHA-256 `845afa9336a5717b6c2ce77fbd4d59e9d5ef69bf86176a4efa970b974fbaa7fb`。仅隐藏了离线浮层，金句/伴读在拔掉电脑后会停在空状态；新用户请优先装全离线版。

## 下载与校验

```bash
# Pages 直链
curl -O https://zhubao315.github.io/zhuocheng-terminal/releases/zhuocheng-offline-2.0.apk
# 或用仓库原始文件
curl -O https://raw.githubusercontent.com/zhubao315/zhuocheng-terminal/main/releases/zhuocheng-offline-2.0.apk

sha256sum zhuocheng-offline-2.0.apk
# 应输出 29f539b64821477f7d93031a770c8183fc8d5a797bcc96639996857dac07c8ec

# 签名指纹（需本机已有 .keys/；签名器 --fingerprint 会拒绝身份不完整）
python scripts/sign_apk_v2.py --fingerprint
python scripts/sign_apk_v2.py --verify <apk>     # 结构 + 摘要 + RSA 验签自校验
```

## 已验证 / 未验证的兼容范围

- ✅ **Android 9**（红米 Note 2 / LineageOS 16）：信息屏 v2.1.2 真机安装成功，打开即全屏停在金句、顶部「拙诚日课」、无顶底导航；金句 20 秒 / 伴读 40 秒自动换新、配置面板开关、长按无选择菜单逐项验证通过
- ✅ **Android 11+ 签名要求**：v2 签名链路验证通过（摘要 / RSA / 证书解析均通过）
- ⚠️ **Xiaomi HyperOS 3.0（Redmi K70）**：系统安装器曾以 `-124` 拒绝侧载，与 APK 架构无关（包内无 native 库）；请关闭纯净模式后用系统文件管理器安装，或开启 USB 调试 + USB 安装后用 `adb install -r` 直装。**尚未完成真机成功安装验证**。
- ⚠️ 其他 Android 版本 / 品牌定制系统：尚未逐一验证

## 升级与密钥

- `.keys/`（私钥 + 自签证书）不入库，需 offline 加密备份；**只丢一个文件时签名器会报错退出，绝不自动生成新身份**（否则旧版本无法覆盖升级）。
- 旧手机若装的是早期仅 v1 签名的版本，升级到本包前需先卸载旧版（签名身份不同）。
- 发布新包前必须更新本文件的 SHA-256、指纹与变更记录。

## 变更记录

- v2.1.2：金句 20 秒 / 伴读 40 秒定时换新（可配置，0 关）；默认字号 1.45 → 1.3；长按不再弹文字选择菜单；真机验证换新与配置闭环
- v2.1.1：修复配置面板关不掉（hidden 属性被作者样式覆盖）
- v2.1.0：信息屏改为手动左右切换、默认停在金句；顶部品牌名；红米 Note 2 真机七张截图替换落地页展示
- v2.0.1：信息屏默认、多端配置、极少互动（自动轮播版，已被 v2.1.0 取代）
- v2.0.0：全离线版 2.0 —— 手机端内置内容引擎与本地档案，零电脑 / 零网络；真机七页截图替换落地页展示
- v1.4.4：隐藏 PhoneBox「电脑未连接 / 点击唤醒」浮层，离线纯净模式；落地页改用真实界面截图
- v1.4.2：新增纯 Python v2 签名器，修复 Android 11+ 安装报错 33
- v1.4.1：Pages 落地页、演示页、品牌命名统一
- v1.4.0：中枢 v2（六任务解耦、每日记录、CLI、19 项测试）
