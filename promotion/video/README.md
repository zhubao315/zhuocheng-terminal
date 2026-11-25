# 拙诚日课 · 产品宣传片

**成片**：`docs/media/zhuocheng-promo.mp4`（20 秒 / 1280×720 / H.264 / ~456 KB）
**海报**：`docs/media/promo-poster.jpg`（第 6 秒抽帧）

## 制作方式

采用 OpenMotion 的 HyperFrames 技术路线：**HTML/CSS 动画 → headless Chrome 逐帧渲染 → FFmpeg 合成 MP4**。

```bash
cd promotion/video
node render.mjs 24 20   # fps, seconds
```

- `scene.html`：分镜与动画（5 幕：旧手机 → 品牌 → 四功能 → 数据 → CTA），`window.renderFrame(t)` 按秒确定性渲染。
- `render.mjs`：CDP 驱动 Chrome，逐帧截图后合成；带异常检测，任何一帧渲染失败即中止。
- 依赖：Node 22.18+、Chrome、FFmpeg。

## 分镜

| 时间 | 画面 |
|------|------|
| 0–4s | 抽屉里的旧手机，还能做什么？ |
| 4–8.5s | 拙诚日课 · 把旧手机变成常亮的修身桌面 |
| 8.5–13.5s | 四张功能卡：离线金句 / AI 伴读 / 日课静坐 / 微习惯中枢 |
| 13.5–17.2s | 999 / 100% / 0 —— 不联网 · 不注册 · 不收集 |
| 17.2–20s | 日日不断 · 拙诚拱卒 + 三个入口 |

## 落地页集成

`docs/index.html` 的 Hero 区下方 `<video controls>` 内嵌，导航新增「影片」锚点 `#film`。

## OpenMotion 说明

OpenMotion Cloud MCP 需要外网访问 `motion.open-design.ai` 并完成浏览器 OAuth 授权；本机无法解析该域名，故采用其同源本地渲染路线产出等价 MP4。若网络就绪，可将 `scene.html` 作为 HyperFrames 工程导入 OpenMotion Studio 继续编辑。
