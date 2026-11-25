import fs from 'node:fs';

const url = process.argv[2];
const cfgPath = process.argv[3];
const cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
const w = new WebSocket(url);
await new Promise(r => w.onopen = r);
let id = 0;
const pending = new Map();
w.onmessage = e => {
  const m = JSON.parse(e.data);
  if (pending.has(m.id)) { pending.get(m.id)(m); pending.delete(m.id); }
};
const send = (method, params = {}) => new Promise(r => {
  const i = ++id;
  pending.set(i, r);
  w.send(JSON.stringify({ id: i, method, params }));
});

const payload = JSON.stringify(cfg);
const expr = `localStorage.setItem('cfg', ${JSON.stringify(payload)}); 'cfg written ' + localStorage.getItem('cfg').length`;
const r = await send('Runtime.evaluate', { expression: expr, returnByValue: true });
console.log('SET:', r.result && r.result.value);
await send('Page.enable');
await send('Page.reload', { ignoreCache: false });
console.log('reloaded');
w.close();
