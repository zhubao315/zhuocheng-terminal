// 从红米 Note 2 真机 WebView 截取信息屏 2.0 的六个模块 + 多端配置面板。
// Usage: node promotion/screen_device_shots.mjs
import { execFileSync } from 'node:child_process';
import { writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const ADB = 'D:\\tmp\\workbuddy-data-cn\\2026-11-23-09-54-19\\flash-hermes\\platform-tools\\adb.exe';
const SERIAL = '192.168.1.66:5555';
const PORT = 9336;
const OUT = path.join(ROOT, 'docs', 'screens');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

const adb = (args) => execFileSync(ADB, args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
adb(['connect', SERIAL]);
const unix = adb(['-s', SERIAL, 'shell', 'cat /proc/net/unix']);
const m = unix.match(/@webview_devtools_remote_(\d+)/);
if (!m) throw new Error('未找到 WebView 调试通道，请先启动应用');
const socket = 'webview_devtools_remote_' + m[1];
adb(['-s', SERIAL, 'forward', 'tcp:' + PORT, 'localabstract:' + socket]);
console.log('CDP socket:', socket);

async function wsUrl() {
  for (let i = 0; i < 40; i++) {
    try {
      const list = await (await fetch('http://127.0.0.1:' + PORT + '/json/list')).json();
      const page = list.find((x) => x.type === 'page') || list[0];
      if (page?.webSocketDebuggerUrl) return page.webSocketDebuggerUrl;
    } catch {}
    await sleep(250);
  }
  throw new Error('CDP 未就绪');
}
const ws = new WebSocket(await wsUrl());
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let id = 0;
const pending = new Map();
ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
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
async function evalJs(expr) {
  const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true });
  if (r.exceptionDetails) throw new Error('EVAL ' + JSON.stringify(r.exceptionDetails));
  return r.result.value;
}
async function shot(file) {
  const r = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  await writeFile(path.join(OUT, file), Buffer.from(r.data, 'base64'));
  console.log('saved', file);
}

await mkdir(OUT, { recursive: true });
await send('Runtime.enable');
await send('Page.enable');

// 选真实内置语料里更有代表性的条目（不造内容）
await evalJs("(function(){var s=ZC.state(),q=ZC_DATA.quotes;for(var i=0;i<q.length;i++){if(q[i].text.indexOf('结硬寨')>=0){s.idx.quote=i;break;}}var c=ZC_DATA.companions;for(var j=0;j<c.length;j++){if(c[j].source==='曾国藩'){s.idx.companion=j;break;}}return [s.idx.quote,s.idx.companion];})()");

const modules = [
  ['quote', '01-信息屏-每日金句.png'],
  ['companion', '02-信息屏-AI伴读.png'],
  ['rike', '03-信息屏-日课十二条.png'],
  ['habit', '04-信息屏-微习惯.png'],
  ['sit', '05-信息屏-静坐三省.png'],
  ['archive', '06-信息屏-成长档案.png']
];
for (const [key, file] of modules) {
  await evalJs("ZC.setConfig({mode:'screen',profile:'note2-landscape',safeTop:0,safeBottom:0,screenScale:1.45,screenSec:20,screenModules:['" + key + "']})");
  await sleep(2600); // 等保存提示消失
  await shot(file);
}
await evalJs("ZC.openConfig()");
await sleep(700);
await shot('07-多端配置.png');
await evalJs("ZC.closeConfig()");

// 验证自动轮播：两屏、每屏 5 秒，等待后应换屏
await evalJs("ZC.setConfig({screenModules:['quote','rike'],screenSec:5})");
const before = await evalJs("ZC.config().at");
await sleep(6200);
const after = await evalJs("ZC.config().at");
console.log('auto-advance:', before, '->', after, before !== after ? 'OK' : 'FAILED');

// 恢复默认六模块，避免真机停留在截图用的单模块状态
await evalJs("ZC.setConfig({mode:'screen',profile:'auto',safeTop:0,safeBottom:0,screenScale:1.45,screenSec:20,screenModules:['quote','companion','rike','habit','sit','archive']})");
await sleep(300);

console.log('all screenshots saved to', OUT);
ws.close();
