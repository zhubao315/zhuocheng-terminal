// 全离线版 2.0 冒烟测试：无头 Chrome CDP 打开 docs/offline.html，逐页验证并截图。
// Usage: node promotion/offline_qa.mjs
import { spawn } from 'node:child_process';
import { writeFile, mkdir, rm } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(__dirname, '..');
const CHROME = 'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe';
const OUT = path.join(__dirname, 'offline-qa');
const URL = 'file:///' + path.join(ROOT, 'docs', 'offline.html').replace(/\\/g, '/');
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

await rm(OUT, { recursive: true, force: true });
await mkdir(OUT, { recursive: true });
const chrome = spawn(CHROME, [
  '--headless=new', '--disable-gpu', '--no-sandbox', '--hide-scrollbars',
  '--remote-debugging-port=9334', '--user-data-dir=' + path.join(OUT, '.profile'),
  '--window-size=1080,1920', '--force-device-scale-factor=1', 'about:blank'
], { stdio: 'ignore' });

async function wsUrl() {
  for (let i = 0; i < 80; i++) {
    try {
      const list = await (await fetch('http://127.0.0.1:9334/json/list')).json();
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
  if (r.exceptionDetails) throw new Error('EVAL: ' + r.exceptionDetails.text);
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
await sleep(1800);

const results = {};
results.title = await evaluate('document.title');
results.overviewQuote = await evaluate("document.getElementById('ovQuote').textContent");
results.counters = await evaluate("document.getElementById('ovCounts').textContent");
results.noOfflineButton = await evaluate("!document.getElementById('wake') && !document.getElementById('offline')");
await shot('01-overview');

await evaluate("ZC.show('quote')");
await sleep(200);
results.quoteText = await evaluate("document.getElementById('qText').textContent");
results.quoteIndex = await evaluate("document.getElementById('qIndex').textContent");
await evaluate("document.getElementById('qNext').click()");
results.quoteAfterNext = await evaluate("document.getElementById('qText').textContent");
await shot('02-quote');

await evaluate("ZC.show('companion')");
await sleep(200);
results.companionPassage = await evaluate("document.getElementById('cPassage').textContent");
results.companionQuestion = await evaluate("document.getElementById('cQuestion').textContent");
await shot('03-companion');

await evaluate("ZC.show('rike')");
await sleep(200);
results.rikeItems = await evaluate("document.querySelectorAll('.rike-item').length");
await evaluate("document.getElementById('rList').children[0].click()");
results.rikeProgress = await evaluate("document.getElementById('rProgress').textContent");
await shot('04-rike');

await evaluate("ZC.show('habit')");
await sleep(200);
results.habitText = await evaluate("document.getElementById('hText').textContent");
await evaluate("document.getElementById('hDone').click()");
results.habitDone = await evaluate("document.getElementById('hCount').textContent");
results.habitStateRaw = await evaluate("JSON.stringify(ZC.state().days[ZC.state().today].habits)");
await sleep(300);
results.habitDoneDelayed = await evaluate("document.getElementById('hCount').textContent");
await shot('05-habit');

await evaluate("ZC.show('sit')");
await sleep(200);
results.sitClock = await evaluate("document.getElementById('sClock').textContent");
await shot('06-sit');

await evaluate("ZC.show('archive')");
await sleep(200);
results.archiveDays = await evaluate("document.getElementById('aDays').textContent");
results.archiveHabits = await evaluate("document.getElementById('aHabits').textContent");
results.localSaved = await evaluate("!!localStorage.getItem('zhuocheng.offline.v2')");
await shot('07-archive');

console.log(JSON.stringify({ results, errors }, null, 2));
ws.close();
chrome.kill();
