// 信息屏「手动左右切换」冒烟测试：默认金句、不自动轮播、六栏目可手动切换、顶部品牌。
// Usage: node promotion/screen_manual_qa.mjs
import { spawn } from 'node:child_process';
import { writeFile, mkdir, rm } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const OUT = path.join(__dirname, 'screen-manual-qa');
const URL = 'file:///' + path.join(ROOT, 'docs', 'offline.html').replace(/\\/g, '/');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

await rm(OUT, { recursive: true, force: true });
await mkdir(OUT, { recursive: true });
const chrome = spawn(CHROME, [
  '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
  '--remote-debugging-port=9341', '--user-data-dir=' + path.join(OUT, '.profile'),
  '--window-size=1920,1080', '--force-device-scale-factor=1', 'about:blank'
], { stdio: 'ignore' });

async function wsUrl() {
  for (let i = 0; i < 80; i++) {
    try {
      const list = await (await fetch('http://127.0.0.1:9341/json/list')).json();
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
    errors.push('EXCEPTION: ' + (d.text || '') + ' | ' + ((d.exception && d.exception.description) || ''));
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
  if (r.exceptionDetails) throw new Error('EVAL: ' + (r.exceptionDetails.text || ''));
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
await sleep(1400);

const results = {};
// 1. 默认停在金句栏目，且是信息屏模式
results.boot = await evaluate("ZC.config()");
results.bootQuoteVisible = await evaluate("document.getElementById('scBody').textContent.indexOf('今日金句') >= 0");
// 2. 顶部显示品牌名，不再有「纯离线 / 信息屏 / 等待推送 / 电脑未连接」
results.topText = await evaluate("(function(){var a=[],els=document.querySelectorAll('#screen .screen-top *');for(var i=0;i<els.length;i++)a.push(els[i].textContent.trim());return a.join(' | ')})()");
results.noOfflineBadge = await evaluate("!document.getElementById('screen').textContent.match(/纯离线|信息屏|等待推送|电脑未连接|点击唤醒/)");
results.noProgressBar = await evaluate("!document.querySelector('.screen-progress') && !document.getElementById('scProgress')");
// 3. 六个栏目条
results.navCount = await evaluate("document.querySelectorAll('#scNav button').length");
results.navLabels = await evaluate("(function(){var a=[],b=document.querySelectorAll('#scNav button');for(var i=0;i<b.length;i++)a.push(b[i].textContent);return a.join(',')})()");
results.navActive = await evaluate("(function(){var b=document.querySelector('#scNav button.active');return b?b.textContent:''})()");
// 4. 不自动轮播：等 4 秒后栏目不变
const before = await evaluate("ZC.config().module");
await sleep(4200);
const after = await evaluate("ZC.config().module");
results.noAutoRotate = { before, after, ok: before === after };
// 5. 手动切换：next / prev / go
await evaluate("ZC.screenNext()");
results.afterNext = await evaluate("ZC.config().module");
await evaluate("ZC.screenPrev()");
results.afterPrev = await evaluate("ZC.config().module");
await evaluate("ZC.screenGo(2)");
results.afterGo2 = await evaluate("ZC.config().module");
results.go2Active = await evaluate("(function(){var b=document.querySelector('#scNav button.active');return b?b.textContent:''})()");
// 6. 点栏目名（真实 DOM 事件）
await evaluate("(function(){var b=document.querySelectorAll('#scNav button')[0];b.click()})()");
results.afterNavClick = await evaluate("ZC.config().module");
// 7. 配置面板：默认栏目下拉存在，无「每屏秒数」
await evaluate("ZC.openConfig()");
await sleep(200);
results.cfgHasStart = await evaluate("!!document.getElementById('cfgStart')");
results.cfgStartValue = await evaluate("document.getElementById('cfgStart').value");
results.cfgNoSec = await evaluate("!document.getElementById('cfgSec') && !document.querySelector('#cfgPanel').textContent.match(/每屏秒数/)");
results.cfgLabel = await evaluate("document.querySelector('#cfgPanel').textContent.indexOf('默认栏目') >= 0");
await shot('config-panel');
await evaluate("ZC.closeConfig()");
// 8. 回到默认金句并截图
await evaluate("ZC.setConfig({mode:'screen',profile:'note2-landscape',ScreenScale:1.45,startModule:'quote',screenModules:['quote','companion','rike','habit','sit','archive']})".replace('ScreenScale', 'screenScale'));
await sleep(300);
await shot('landscape-quote-default');
await evaluate("ZC.screenGo(2)");
await sleep(200);
await shot('landscape-rike-manual');
await evaluate("ZC.screenGo(0)");
// 9. 竖屏
await send('Emulation.setDeviceMetricsOverride', { width: 1080, height: 1920, deviceScaleFactor: 1, mobile: false });
await sleep(300);
await shot('portrait-quote-default');
results.portraitNav = await evaluate("document.querySelectorAll('#scNav button').length");

const pass = results.boot.module === 'quote' && results.boot.at === 0 &&
  results.noOfflineBadge && results.noProgressBar && results.navCount === 6 &&
  results.noAutoRotate.ok && results.afterNext === 'companion' && results.afterPrev === 'quote' &&
  results.afterGo2 === 'rike' && results.afterNavClick === 'quote' &&
  results.cfgHasStart && results.cfgNoSec && results.cfgStartValue === 'quote' && errors.length === 0;

console.log(JSON.stringify(results, null, 2));
console.log('errors:', errors.length ? errors.join('\n') : 'none');
console.log(pass ? 'RESULT: PASS' : 'RESULT: FAIL');
ws.close();
chrome.kill();
process.exit(pass ? 0 : 1);
