// 信息屏模式布局回归：无头 Chrome CDP 逐栏目截图 + 多端配置验证。
// 信息屏为静态常亮屏，默认停在金句，六栏目靠手动左右切换（不自动轮播）。
// Usage: node promotion/screen_qa.mjs
import { spawn } from 'node:child_process';
import { writeFile, mkdir, rm } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const OUT = path.join(__dirname, 'screen-qa');
const URL = 'file:///' + path.join(ROOT, 'docs', 'offline.html').replace(/\\/g, '/');
const MODULES = ['quote', 'companion', 'rike', 'habit', 'sit', 'archive'];
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

await rm(OUT, { recursive: true, force: true });
await mkdir(OUT, { recursive: true });
const chrome = spawn(CHROME, [
  '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
  '--remote-debugging-port=9337', '--user-data-dir=' + path.join(OUT, '.profile'),
  '--window-size=1920,1080', '--force-device-scale-factor=1', 'about:blank'
], { stdio: 'ignore' });

async function wsUrl() {
  for (let i = 0; i < 80; i++) {
    try {
      const list = await (await fetch('http://127.0.0.1:9337/json/list')).json();
      const page = list.find((x) => x.type === 'page');
      if (page?.webSocketDebuggerUrl) return page.webSocketDebuggerUrl;
    } catch {}
    await sleep(250);
  }
  throw new Error('CDP not ready');
}
const ws = new WebSocket(await wsUrl());
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let id = 0;
const pending = new Map();
const errors = [];
ws.onmessage = (e) => {
  const m = JSON.parse(e.data);
  if (m.id && pending.has(m.id)) {
    const { res, rej } = pending.get(m.id);
    pending.delete(m.id);
    m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result);
  }
  if (m.method === 'Runtime.exceptionThrown') {
    const d = m.params.exceptionDetails;
    errors.push('EXCEPTION: ' + (d.text || '') + ' | ' + ((d.exception && d.exception.description) || '') + ' | ' + (d.url || '') + ':' + (d.lineNumber || 0));
  }
  if (m.method === 'Log.entryAdded' && m.params.entry.level === 'error') errors.push('LOG: ' + m.params.entry.text);
};
function send(method, params = {}) {
  return new Promise((res, rej) => {
    const mid = ++id;
    pending.set(mid, { res, rej });
    ws.send(JSON.stringify({ id: mid, method, params }));
  });
}
async function evaluate(expr) {
  const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true, awaitPromise: true });
  if (r.exceptionDetails) throw new Error('EVAL: ' + (r.exceptionDetails.text || '') + ' ' + (r.exceptionDetails.exception?.description || ''));
  return r.result.value;
}
async function shot(name) {
  const r = await send('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false });
  await writeFile(path.join(OUT, name + '.png'), Buffer.from(r.data, 'base64'));
}

await send('Runtime.enable');
await send('Log.enable');
await send('Page.enable');
await send('Page.navigate', { url: URL });
await sleep(1500);

const results = {};
results.mode = await evaluate("ZC.config().mode");
results.profile = await evaluate("ZC.config().profile");
results.scale = await evaluate("ZC.config().scale");
results.barHidden = await evaluate("getComputedStyle(document.getElementById('topbar')).display === 'none'");
results.tabsHidden = await evaluate("getComputedStyle(document.getElementById('tabs')).display === 'none'");
results.noWake = await evaluate("!document.getElementById('wake') && !document.getElementById('offline')");

for (const key of MODULES) {
  await evaluate("ZC.setConfig({profile:'note2-landscape',screenModules:['" + key + "']})");
  await sleep(250);
  const info = await evaluate("(function(){var b=document.getElementById('scBody');return {text:(b.textContent||'').replace(/\\s+/g,' ').slice(0,90),overflow:b.scrollHeight-b.clientHeight,at:ZC.config().at}})()");
  results[key] = info;
  await shot('landscape-' + key);
}

// 配置抽屉：改留白与字号，验证即时生效
await evaluate("ZC.openConfig()");
await sleep(200);
await shot('config-panel');
results.configOpen = await evaluate("!document.getElementById('cfgPanel').hidden");
await evaluate("(function(){document.getElementById('cfgTop').value=32;document.getElementById('cfgBottom').value=28;document.getElementById('cfgScale').value=1.6;document.getElementById('cfgSave').click();})()");
await sleep(200);
results.afterSave = await evaluate("ZC.config()");
results.safeApplied = await evaluate("getComputedStyle(document.documentElement).getPropertyValue('--safe-top').trim()");

// 竖屏预设验证
await send('Emulation.setDeviceMetricsOverride', { width: 1080, height: 1920, deviceScaleFactor: 1, mobile: false });
await evaluate("ZC.setConfig({profile:'note2-portrait',safeTop:0,safeBottom:0,screenScale:1.15,screenModules:['quote','companion','rike','habit','sit','archive']})");
await sleep(300);
results.portrait = await evaluate("(function(){var b=document.getElementById('scBody');return {profile:ZC.config().profile,overflow:b.scrollHeight-b.clientHeight,text:(b.textContent||'').replace(/\\s+/g,' ').slice(0,60)}})()");
await shot('portrait-quote');

console.log(JSON.stringify(results, null, 2));
console.log('errors:', errors.length ? errors.join('\n') : 'none');
ws.close();
chrome.kill();
