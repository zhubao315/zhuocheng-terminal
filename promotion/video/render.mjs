// OpenMotion-style HyperFrames renderer
// scene.html (HTML/CSS/JS) -> headless Chrome CDP frames -> FFmpeg MP4
// Usage: node render.mjs [fps] [seconds]
import { spawn } from 'node:child_process';
import { writeFile, mkdir, readdir, rm } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const FPS = Number(process.argv[2] || 24);
const SECONDS = Number(process.argv[3] || 20);
const FRAMES = FPS * SECONDS;
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const FRAME_DIR = path.join(__dirname, 'frames');
const SCENE = 'file:///' + path.join(__dirname, 'scene.html').replace(/\\/g, '/');
const OUT_MP4 = path.join(__dirname, '..', '..', 'docs', 'media', 'zhuocheng-promo.mp4');

const sleep = (ms) => new Promise(r => setTimeout(r, ms));

await rm(FRAME_DIR, { recursive: true, force: true });
await mkdir(FRAME_DIR, { recursive: true });
await mkdir(path.dirname(OUT_MP4), { recursive: true });

// Launch Chrome with remote debugging on a dedicated profile
const profile = path.join(__dirname, '.chrome-profile');
const chrome = spawn(CHROME, [
  '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
  '--remote-debugging-port=9333', '--user-data-dir=' + profile,
  '--window-size=1280,720', '--force-device-scale-factor=1',
  'about:blank'
], { stdio: 'ignore' });

async function getWsUrl() {
  for (let i = 0; i < 60; i++) {
    try {
      const res = await fetch('http://127.0.0.1:9333/json/list');
      const list = await res.json();
      const page = list.find(x => x.type === 'page');
      if (page?.webSocketDebuggerUrl) return page.webSocketDebuggerUrl;
    } catch {}
    await sleep(300);
  }
  throw new Error('Chrome DevTools endpoint not ready');
}

const ws = new WebSocket(await getWsUrl());
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let id = 0;
const pending = new Map();
ws.onmessage = (ev) => {
  const msg = JSON.parse(ev.data);
  if (msg.id && pending.has(msg.id)) {
    const { res, rej } = pending.get(msg.id);
    pending.delete(msg.id);
    msg.error ? rej(new Error(JSON.stringify(msg.error))) : res(msg.result);
  }
};
function send(method, params = {}) {
  return new Promise((res, rej) => {
    const mid = ++id;
    pending.set(mid, { res, rej });
    ws.send(JSON.stringify({ id: mid, method, params }));
  });
}

await send('Page.enable');
await send('Runtime.enable');
await send('Emulation.setDeviceMetricsOverride', {
  width: 1280, height: 720, deviceScaleFactor: 1, mobile: false
});
await send('Page.navigate', { url: SCENE });
for (let i = 0; i < 50; i++) {
  const r = await send('Runtime.evaluate', { expression: 'typeof window.renderFrame', returnByValue: true });
  if (r.result.value === 'function') break;
  await sleep(200);
}

console.log(`Rendering ${FRAMES} frames @ ${FPS}fps (${SECONDS}s)...`);
for (let f = 0; f < FRAMES; f++) {
  const t = (f / FPS);
  const ev = await send('Runtime.evaluate', {
    expression: `try { window.renderFrame(${t.toFixed(6)}); 'OK' } catch (e) { String(e && e.stack || e) }`,
    returnByValue: true
  });
  if (ev.exceptionDetails || (ev.result?.value && ev.result.value !== 'OK')) {
    throw new Error('renderFrame failed at frame ' + f + ': ' + JSON.stringify(ev.result?.value || ev.exceptionDetails));
  }
  const shot = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  const file = path.join(FRAME_DIR, `f${String(f).padStart(5, '0')}.png`);
  await writeFile(file, Buffer.from(shot.data, 'base64'));
  if (f % 60 === 0) console.log(`  frame ${f}/${FRAMES}`);
}
ws.close();
chrome.kill();
await sleep(500);

console.log('Encoding MP4 with FFmpeg...');
await new Promise((res, rej) => {
  const ff = spawn('ffmpeg', [
    '-y', '-framerate', String(FPS), '-i', path.join(FRAME_DIR, 'f%05d.png'),
    '-c:v', 'libx264', '-preset', 'medium', '-crf', '21',
    '-pix_fmt', 'yuv420p', '-movflags', '+faststart',
    '-vf', 'scale=1280:720', OUT_MP4
  ], { stdio: 'inherit' });
  ff.on('exit', (code) => code === 0 ? res() : rej(new Error('ffmpeg exit ' + code)));
});

await rm(FRAME_DIR, { recursive: true, force: true });
await rm(profile, { recursive: true, force: true });
console.log('DONE:', OUT_MP4);
