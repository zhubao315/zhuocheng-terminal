// 从红米 Note 2 真机 WebView 截取信息屏 2.1 的六个栏目 + 多端配置面板。
// 信息屏：默认停在金句，不自动轮播，六个栏目手动左右切换。
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
const errors = [];
ws.onmessage = (e) => {
  const msg = JSON.parse(e.data);
  if (msg.id && pending.has(msg.id)) {
    const { res, rej } = pending.get(msg.id);
    pending.delete(msg.id);
    msg.error ? rej(new Error(JSON.stringify(msg.error))) : res(msg.result);
  }
  if (msg.method === 'Runtime.exceptionThrown') errors.push('EXCEPTION ' + (msg.params.exceptionDetails.text || ''));
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

// 固定为六个栏目 + 横屏预设，保证每张图都能看到完整栏目切换条
await evalJs("ZC.setConfig({mode:'screen',profile:'note2-landscape',safeTop:0,safeBottom:0,screenScale:1.45,startModule:'quote',screenModules:['quote','companion','rike','habit','sit','archive']})");
// 选真实内置语料里更有代表性的条目（不造内容）
await evalJs("(function(){var s=ZC.state(),q=ZC_DATA.quotes;for(var i=0;i<q.length;i++){if(q[i].text.indexOf('结硬寨')>=0){s.idx.quote=i;break;}}var c=ZC_DATA.companions;for(var j=0;j<c.length;j++){if(c[j].source==='曾国藩'){s.idx.companion=j;break;}}ZC.screenGo(0);return [s.idx.quote,s.idx.companion];})()");

const modules = [
  [0, '01-信息屏-每日金句.png'],
  [1, '02-信息屏-AI伴读.png'],
  [2, '03-信息屏-日课十二条.png'],
  [3, '04-信息屏-微习惯.png'],
  [4, '05-信息屏-静坐三省.png'],
  [5, '06-信息屏-成长档案.png']
];
for (const [i, file] of modules) {
  await evalJs('ZC.screenGo(' + i + ')');
  await sleep(500);
  await shot(file);
}
await evalJs('ZC.openConfig()');
await sleep(500);
await shot('07-多端配置.png');
await evalJs('ZC.closeConfig()');

// 验证：默认停在金句、不自动轮播、手动左右切换有效
await evalJs("ZC.setConfig({startModule:'quote',screenModules:['quote','companion','rike','habit','sit','archive']})");
const boot = await evalJs('ZC.config().module');
await sleep(4200);
const still = await evalJs('ZC.config().module');
await evalJs('ZC.screenNext()');
const next = await evalJs('ZC.config().module');
await evalJs('ZC.screenGo(0)');
const home = await evalJs('ZC.config().module');
console.log('default quote:', boot, '| no auto-rotate after 4.2s:', still,
  '| manual next:', next, '| back home:', home);
console.log('CHECK:', boot === 'quote' && still === 'quote' && next === 'companion' && home === 'quote' ? 'PASS' : 'FAIL');

// 收尾：恢复默认，停在金句
await evalJs("ZC.setConfig({mode:'screen',profile:'auto',safeTop:0,safeBottom:0,screenScale:1.45,startModule:'quote',screenModules:['quote','companion','rike','habit','sit','archive']})");
console.log('errors:', errors.length ? errors.join('\n') : 'none');
console.log('all screenshots saved to', OUT);
ws.close();
