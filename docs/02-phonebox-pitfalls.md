# 02 · PhoneBox 踩坑指南（血泪经验）

本项目在与 PhoneBox + 老旧 Android WebView 搏斗过程中踩过的坑，全部记录在此。
如果你也要在旧手机上跑 HTML 组件面板，先读完这一篇，能省下大量调试时间。

原型环境：红米 Note 2 / LineageOS 16 (Android 9) / 系统 WebView 内核 Chromium 80。

## 1. HTML 组件是「独立 iframe」渲染

HTML 组件按**组件自身尺寸**建立独立视口。这意味着：

- `vh` / `vw` 相对的是**组件的宽高**，不是手机屏幕！
- 一个 `h:2`（两格高）的组件里写 `font-size: 22vh`，实际效果是组件高度的 22%。
- 所有字号都要按「组件视口」重新标定，不能照搬直觉。

## 2. Chromium 80 不支持容器查询单位（cq）

`cqw`、`cqh` 等容器单位在 Chromium 80 上会被当作非法值，整条 CSS 规则失效。
**只能用 `vh` / `vw` + `clamp()`**。顺带一提：面板顶部「WebView 版本过旧」黄条正是
PhoneBox 检测到内核过老所致——若要去掉，修改 APK 内 `index.html` 中的检测逻辑并重签名
（见第 7 条）。

## 3. push 组件文本写死 `white-space: nowrap` + 省略号

push 组件（`.pv`）单行显示，长文本必然被截断成 `……`。长内容（比如超过一行的金句、
伴读原文）**必须改用 HTML 组件**，配合：

```css
overflow-wrap: break-word;
word-break: break-word;
```

即可自动换行，无论句子多长都完整可见。

## 4. 重复 id 会被 PhoneBox 自动改名 → 「重影」

往同一页面重复追加同 id 的 HTML 组件，PhoneBox 会把新组件改名为 `-h-2`、`-h-3`…
然后**全部叠加渲染**。症状是文字出现多层重影，极易误判为 WebView 重绘残影
（我们试过 `translateZ(0)`、克隆节点替换，全部无效——因为根本不是渲染问题）。

解法：部署脚本里**按 id 前缀先清旧再追加**，保证同 id 组件只有一份。

## 5. 动态更新文本要换节点，不能只改 textContent？

实测：直接改 `textContent` 在部分内核上不触发重绘，保险做法是 `cloneNode` 替换：

```js
function put(id, txt) {
  var e = document.getElementById(id);
  if (e.textContent === txt) return;
  var n = e.cloneNode(false);
  n.textContent = txt;
  e.parentNode.replaceChild(n, e);
}
```

（注意：重影的真正根因是第 4 条，本条只是让更新更稳。）

## 6. 切页有 15 秒「温柔切换」保护

`/api/goto/<page>` 切页后，若页面加载不足 15 秒，跳转可能被吞。
批量部署/截图验证时：**每步之间 sleep 17–20 秒**，或补发一次 goto。

## 7. 改已安装 APK 的内容会被 PM 校验移除

直接修改已安装 APK 里的文件再放回去，Android 包管理器校验失败会直接移除应用。
必须**重新签名**。本项目自带纯 Python 的 v1 签名器 `scripts/sign_apk.py`
（基于 cryptography 库实现 per-entry digest、NoCapabilities），无需 JDK。

## 8. 手机反复锁屏

床头终端必须常亮：

```
adb shell settings put system screen_off_timeout 2147483647
```

## 9. WiFi adb：拔掉数据线照常采集

```bash
# 一次性设置（重启后自动生效）
adb shell setprop persist.adb.tcp.port 5555
adb tcpip 5555
adb connect <手机IP>:5555
```

中枢里每拍检查设备在线状态，离线时自动 `adb connect` 重连。

## 10. 横屏坐标

`screencap` 输出 1920×1080（横屏），`input tap` 也用横屏坐标系。
日课清单第一列第一个勾选框约在 (133, 400)，第二行 (133, 448)。

## 11. 伴读页布局

- 原文区用 `h:2` 的 HTML 组件，字号 `min(22vh, 8vw)`（组件视口！）。
- 解读用 push 的 list 样式，中文长句先按标点切分、重组到每行 ≤32 字，避免省略号。
- 底部组件容易被屏幕边缘裁掉，问题（思考题）并入解读列表而不是独立组件。

## 12. 中文长句拆行算法

list 组件按行渲染，中文没有空格可断。`ai_companion.group_fragments()` 按中文标点
（。；，、：）切句再贪心合并到每行不超过指定宽度，实测在各种长度的解读文本上都不会出现省略号。

---

有新坑欢迎 PR 补充到本文档。
