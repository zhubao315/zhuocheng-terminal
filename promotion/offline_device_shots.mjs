// 从真机 WebView 直接截取全离线版 2.0 的七个页面，写入 docs/screens/。
// Usage: node promotion/offline_device_shots.mjs
import { execFileSync } from 'node:child_process';
import { writeFile, mkdir } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const ADB = 'D:\\tmp\\workbuddy-data-cn\\2026-11-23-09-54-19\\flash-hermes\\platform-tools\\adb.exe';
const SERIAL = '192.168.1.66:5555';
const PORT = 9335;
const OUT = path.join(ROOT, 'docs', 'screens');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

function adb(args) {
  return execFileSync(ADB, args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
}

adb(['connect', SERIAL]);
const unix = adb(['-s', SERIAL, 'shell', 'cat /proc/net/unix']);
const m = unix.match(/@webview_devtools_remote_(\d+)/);
if (!m) throw new Error('未找到 WebView 调试通道');
const socket = 'webview_devtools_remote_' + m[1];
adb(['-s', SERIAL, 'forward', 'tcp:' + PORT, 'localabstract:' + socket]);
console.log('CDP socket:', socket);

async function wsUrl() {
  for (let i = 0; i < 40; i++) {
    try {
      const list = await (await fetch('http://127.0.0.1:' + PORT + '/json/list')).json();
      const page = list.find((x) => x.type === 'page' && x.url.indexOf('offline') >= 0) || list.find((x) => x.type === 'page');
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

// 选择真实语料里更有代表性的条目（仍是内置原文，不造内容）
await evalJs("(function(){var s=ZC.state();var q=ZC_DATA.quotes;for(var i=0;i<q.length;i++){if(q[i].text.indexOf('结硬寨')>=0){s.idx.quote=i;break;}}var c=ZC_DATA.companions;for(var j=0;j<c.length;j++){if(c[j].source==='曾国藩'){s.idx.companion=j;break;}}return [s.idx.quote,s.idx.companion];})()");

await evalJs("ZC.show('overview')");
await sleep(400);
await shot('01-终端总览.png');

await evalJs("ZC.show('quote')");
await sleep(300);
await shot('02-每日金句.png');

await evalJs("ZC.show('companion')");
await sleep(300);
await shot('03-AI伴读.png');

await evalJs("ZC.show('rike');document.getElementById('rList').children[0].click();document.getElementById('rList').children[1].click();document.getElementById('rList').children[2].click();");
await sleep(300);
await shot('04-日课打卡.png');

await evalJs("ZC.show('habit')");
await sleep(300);
await shot('05-微习惯.png');

await evalJs("ZC.show('sit')");
await sleep(300);
await shot('06-静坐三省.png');

await evalJs("ZC.show('archive')");
await sleep(300);
await shot('07-成长档案.png');

console.log('all screenshots saved to', OUT);
ws.close();
