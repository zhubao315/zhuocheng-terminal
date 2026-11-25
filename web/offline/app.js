/* 拙诚日课终端 · 全离线版 2.0
   所有内容来自内嵌 DATA，所有状态存于 localStorage。
   不访问网络、不调用 API、不依赖电脑端。兼容 Chromium 80 级 WebView。 */
(function () {
  'use strict';

  var KEY = 'zhuocheng.offline.v2';
  var D = window.ZC_DATA || { quotes: [], companions: [], microhabits: [], rike: [], reminders: [] };
  var PAGES = ['overview', 'quote', 'companion', 'rike', 'habit', 'sit', 'archive'];
  var $ = function (id) { return document.getElementById(id); };
  var currentPage = 'overview';
  var viewDate = '';
  var bootAt = Date.now();
  var lastRun = { quote: bootAt, companion: bootAt, habit: bootAt };
  var toastTimer = null;
  var sitMin = 10, sitLeft = 600, sitRunning = false, sitTimer = null;
  var sitDone = [false, false, false];

  function pad(n) { return n < 10 ? '0' + n : '' + n; }
  function dateKey(d) { return d.getFullYear() + '-' + pad(d.getMonth() + 1) + '-' + pad(d.getDate()); }
  function shiftDate(key, delta) {
    var p = key.split('-');
    var d = new Date(parseInt(p[0], 10), parseInt(p[1], 10) - 1, parseInt(p[2], 10));
    d.setDate(d.getDate() + delta);
    return dateKey(d);
  }
  function weekText(d) { return ['日', '一', '二', '三', '四', '五', '六'][d.getDay()]; }
  function mmss(sec) {
    sec = Math.max(0, Math.floor(sec));
    return pad(Math.floor(sec / 60)) + ':' + pad(sec % 60);
  }
  function esc(s) {
    return String(s == null ? '' : s).replace(/&/g, '&amp;').replace(/</g, '&lt;')
      .replace(/>/g, '&gt;').replace(/"/g, '&quot;').replace(/'/g, '&#39;');
  }
  function toast(msg) {
    var el = $('toast');
    if (!el) return;
    el.textContent = msg;
    el.className = 'show';
    if (toastTimer) clearTimeout(toastTimer);
    toastTimer = setTimeout(function () { el.className = ''; }, 2200);
  }

  function defaults() {
    return {
      v: 2,
      today: dateKey(new Date()),
      settings: { theme: 'dark', fontScale: 1, quoteSec: 180, companionSec: 600, habitSec: 3600 },
      idx: { quote: 0, companion: 0, habit: 0 },
      paused: { quote: false, companion: false, habit: false },
      days: {},
      favs: { quote: [], companion: [] }
    };
  }

  function load() {
    var s = null;
    try {
      var raw = localStorage.getItem(KEY);
      if (raw) s = JSON.parse(raw);
    } catch (e) { s = null; }
    if (!s || s.v !== 2) s = defaults();
    var d = defaults();
    if (!s.settings) s.settings = d.settings;
    if (!s.idx) s.idx = d.idx;
    if (!s.paused) s.paused = d.paused;
    if (!s.days) s.days = {};
    if (!s.favs) s.favs = d.favs;
    for (var k in d.settings) { if (s.settings[k] == null) s.settings[k] = d.settings[k]; }
    for (var t in d.idx) { if (s.idx[t] == null) s.idx[t] = 0; }
    for (var p in d.paused) { if (s.paused[p] == null) s.paused[p] = false; }
    if (!s.favs.quote) s.favs.quote = [];
    if (!s.favs.companion) s.favs.companion = [];
    return s;
  }

  var S = load();

  function save() {
    try { localStorage.setItem(KEY, JSON.stringify(S)); }
    catch (e) { toast('本机存储不可用，本次修改仅在当前页面有效'); }
  }

  function ensureDay(key) {
    if (!S.days[key]) S.days[key] = { rike: {}, habits: {}, sits: [], notes: [] };
    var d = S.days[key];
    if (!d.rike) d.rike = {};
    if (!d.habits) d.habits = {};
    if (!d.sits) d.sits = [];
    if (!d.notes) d.notes = [];
    return d;
  }

  function today() {
    var k = dateKey(new Date());
    if (S.today !== k) { S.today = k; save(); }
    ensureDay(k);
    return k;
  }

  function list(type) {
    if (type === 'quote') return D.quotes || [];
    if (type === 'companion') return D.companions || [];
    if (type === 'habit') return D.microhabits || [];
    return [];
  }
  function current(type) {
    var a = list(type);
    if (!a.length) return {};
    var i = S.idx[type] % a.length;
    if (i < 0) i = 0;
    return a[i];
  }
  function advance(type, silent) {
    var a = list(type);
    if (a.length < 2) return;
    var cur = S.idx[type] % a.length;
    var n = cur + 1 + Math.floor(Math.random() * (a.length - 1));
    if (n % a.length === cur) n = cur + 1;
    S.idx[type] = n % a.length;
    lastRun[type] = Date.now();
    save();
    if (!silent) renderPage(currentPage);
  }
  function step(type, delta) {
    var a = list(type);
    if (!a.length) return;
    S.idx[type] = (S.idx[type] + delta + a.length) % a.length;
    lastRun[type] = Date.now();
    save();
    renderPage(currentPage);
  }
  function rikeDone(key) {
    var d = S.days[key];
    if (!d || !d.rike) return 0;
    var n = 0;
    for (var i in d.rike) { if (d.rike[i]) n++; }
    return n;
  }
  function activeDays() {
    var arr = [];
    for (var k in S.days) {
      var d = S.days[k];
      var any = rikeDone(k) > 0 || d.sits.length > 0;
      if (!any) {
        for (var h in d.habits) { if (d.habits[h] === 'done') { any = true; break; } }
      }
      if (any) arr.push(k);
    }
    return arr.sort();
  }
  function streak() {
    var set = {};
    var days = activeDays();
    for (var i = 0; i < days.length; i++) set[days[i]] = 1;
    var k = today(), n = 0;
    while (set[k]) { n++; k = shiftDate(k, -1); }
    return n;
  }

  function applyTheme() {
    var light = S.settings.theme === 'light';
    document.body.className = light ? 'light' : '';
    $('themeBtn').textContent = light ? '夜间' : '日间';
  }

  /* ---------------- 页面渲染 ---------------- */

  function renderOverview() {
    var q = current('quote'), h = current('habit'), d = ensureDay(today());
    var now = new Date();
    $('ovDate').textContent = now.getFullYear() + ' 年 ' + (now.getMonth() + 1) + ' 月 ' + now.getDate() + ' 日 · 星期' + weekText(now);
    $('ovTheme').textContent = '今日主题 · ' + (q.tag || h.maps || '拙诚日课');
    $('ovQuote').textContent = q.text || '—';
    $('ovSource').textContent = (q.source || '—') + (q.tag ? ' · ' + q.tag : '');
    var n = rikeDone(today());
    $('ovRike').textContent = n + ' / ' + (D.rike.length || 12);
    $('ovRikeBar').style.width = Math.round(n / (D.rike.length || 12) * 100) + '%';
    $('ovHabit').textContent = h.habit || '—';
    $('ovHabitMap').textContent = h.maps ? '对应日课 · ' + h.maps : '—';
    $('ovSit').textContent = '今日 ' + d.sits.length + ' 次';
    $('ovStreak').textContent = '连续 ' + streak() + ' 天';
    $('ovCounts').textContent = (D.quotes.length || 0) + ' / ' + (D.companions.length || 0);
    $('ovUptime').textContent = Math.floor((Date.now() - bootAt) / 60000) + ' 分 ' + Math.floor((Date.now() - bootAt) / 1000 % 60) + ' 秒';
  }

  function renderQuote() {
    var q = current('quote');
    $('qText').textContent = q.text || '—';
    $('qText').style.fontSize = Math.round(30 * S.settings.fontScale) + 'px';
    $('qMeta').textContent = (q.source || '—') + (q.tag ? ' · ' + q.tag : '');
    $('qIndex').textContent = (S.idx.quote + 1) + ' / ' + (D.quotes.length || 0);
    $('qPause').textContent = S.paused.quote ? '继续' : '暂停';
    var fav = S.favs.quote.indexOf(S.idx.quote) >= 0;
    $('qFav').textContent = fav ? '已收藏 ✓' : '收藏';
    $('qNextInfo').textContent = '每 ' + S.settings.quoteSec + ' 秒自动换新；组内可随时暂停、翻阅、收藏。';
  }

  function renderCompanion() {
    var c = current('companion');
    $('cPassage').textContent = c.passage || '—';
    $('cSource').textContent = c.source || '—';
    $('cInsight').textContent = c.insight || '—';
    $('cQuestion').textContent = c.question || '—';
    $('cPractice').textContent = '关联日课 · ' + (c.practice || '静坐');
    $('cIndex').textContent = (S.idx.companion + 1) + ' / ' + (D.companions.length || 0);
    $('cPause').textContent = S.paused.companion ? '继续' : '暂停';
    var fav = S.favs.companion.indexOf(S.idx.companion) >= 0;
    $('cFav').textContent = fav ? '已收藏 ✓' : '收藏';
    $('cNextInfo').textContent = '每 ' + S.settings.companionSec + ' 秒自动换新。解读为构建期预生成，运行时不调用任何 API。';
  }

  function renderRike() {
    var d = ensureDay(viewDate);
    var items = D.rike || [];
    var html = '';
    for (var i = 0; i < items.length; i++) {
      var done = !!d.rike[i];
      html += '<div class="rike-item' + (done ? ' done' : '') + '" data-i="' + i + '">' +
        '<span class="tick">' + (done ? '✓' : '') + '</span>' + esc(items[i]) + '</div>';
    }
    $('rList').innerHTML = html;
    var n = rikeDone(viewDate);
    $('rProgress').textContent = n + ' / ' + items.length;
    $('rBar').style.width = Math.round(n / (items.length || 12) * 100) + '%';
    $('rDate').textContent = viewDate + (viewDate === today() ? '（今天）' : '');
    $('rNextDay').disabled = viewDate >= today();
  }

  function renderHabit() {
    var h = current('habit');
    var d = ensureDay(today());
    var st = d.habits[S.idx.habit];
    $('hText').textContent = h.habit || '—';
    $('hMap').textContent = '日课 · ' + (h.maps || '—');
    $('hDur').textContent = (h.duration_minutes || 2) + ' 分钟';
    $('hLevel').textContent = h.difficulty === 'easy' ? '轻松' : (h.difficulty === 'hard' ? '进阶' : '适中');
    var done = 0;
    for (var k in d.habits) { if (d.habits[k] === 'done') done++; }
    $('hCount').textContent = '今日完成 ' + done;
    $('hDone').textContent = st === 'done' ? '已完成 ✓' : '完成';
    $('hPause').textContent = S.paused.habit ? '继续轮换' : '暂停轮换';
    $('hNextInfo').textContent = '每 ' + Math.round(S.settings.habitSec / 60) + ' 分钟换一条；状态：' +
      (st === 'done' ? '已完成' : st === 'later' ? '稍后' : st === 'skip' ? '跳过' : '待办') + '。';
  }

  function renderSit() {
    $('sClock').textContent = mmss(sitLeft);
    $('sStatus').textContent = sitRunning ? '进行中' : (sitLeft < sitMin * 60 ? '已暂停' : '未开始');
    $('sCircle').className = sitRunning ? 'breath running' : 'breath';
    $('sStart').textContent = sitLeft < sitMin * 60 ? '继续' : '开始';
  }

  function renderArchive() {
    var days = activeDays(), k, n = 0, minutes = 0, habits = 0;
    for (var i = 0; i < days.length; i++) {
      var d = S.days[days[i]];
      for (var j = 0; j < d.sits.length; j++) { n++; minutes += (d.sits[j].minutes || 0); }
      for (var h in d.habits) { if (d.habits[h] === 'done') habits++; }
    }
    $('aDays').textContent = days.length;
    $('aStreak').textContent = streak();
    $('aHabits').textContent = habits;
    $('aSits').textContent = n + ' / ' + minutes;

    var base = today(), html = '';
    for (var b = 6; b >= 0; b--) {
      var key = shiftDate(base, -b);
      var done = rikeDone(key);
      var pct = Math.round(done / (D.rike.length || 12) * 100);
      html += '<div class="week-row"><span>' + key.slice(5) + '</span><div class="week-bar"><i style="width:' +
        pct + '%"></i></div><b>' + done + '/12</b></div>';
    }
    $('aWeek').innerHTML = html;

    var fhtml = '', count = 0;
    for (var f = S.favs.quote.length - 1; f >= 0 && count < 12; f--, count++) {
      var q = D.quotes[S.favs.quote[f]];
      if (q) fhtml += '<div class="fav-item">金句 · ' + esc(q.text).slice(0, 34) +
        '<button type="button" data-type="quote" data-i="' + S.favs.quote[f] + '">查看</button></div>';
    }
    for (var c = S.favs.companion.length - 1; c >= 0 && count < 20; c--, count++) {
      var co = D.companions[S.favs.companion[c]];
      if (co) fhtml += '<div class="fav-item">伴读 · ' + esc(co.passage).slice(0, 34) +
        '<button type="button" data-type="companion" data-i="' + S.favs.companion[c] + '">查看</button></div>';
    }
    $('aFavs').innerHTML = fhtml || '暂无收藏';
  }

  function renderPage(page) {
    currentPage = page;
    var i;
    for (i = 0; i < PAGES.length; i++) {
      var el = $('page-' + PAGES[i]);
      if (el) el.hidden = (PAGES[i] !== page);
    }
    var tabs = $('tabs').getElementsByTagName('button');
    for (i = 0; i < tabs.length; i++) {
      tabs[i].className = tabs[i].getAttribute('data-page') === page ? 'active' : '';
    }
    if (page === 'overview') renderOverview();
    else if (page === 'quote') renderQuote();
    else if (page === 'companion') renderCompanion();
    else if (page === 'rike') { if (!viewDate) viewDate = today(); renderRike(); }
    else if (page === 'habit') renderHabit();
    else if (page === 'sit') renderSit();
    else if (page === 'archive') renderArchive();
  }

  function show(page) {
    if (PAGES.indexOf(page) < 0) page = 'overview';
    if (page === 'rike') viewDate = today();
    renderPage(page);
    $('main').scrollTop = 0;
    try { window.location.hash = page; } catch (e) { /* file:// 下可能受限 */ }
  }

  /* ---------------- 交互 ---------------- */

  function toggleFav(type) {
    var arr = S.favs[type], i = S.idx[type];
    var at = arr.indexOf(i);
    if (at >= 0) { arr.splice(at, 1); toast('已取消收藏'); }
    else { arr.push(i); toast('已收藏到本机成长档案'); }
    save();
    renderPage(currentPage);
  }

  function setHabitStatus(status, moveNext) {
    ensureDay(today()).habits[S.idx.habit] = status;
    save();
    toast(status === 'done' ? '已记录完成' : status === 'later' ? '已标记稍后' : '已跳过');
    if (moveNext) advance('habit', true);
    renderPage(currentPage);
  }

  function buildMarkdown() {
    var lines = ['# 拙诚日课终端 · 成长档案', '', '导出时间：' + new Date().toLocaleString(), '',
      '> 所有数据来自本机记录；无记录的日期不生成结论。', '', '## 总览', '',
      '- 有记录天数：' + activeDays().length, '- 连续天数：' + streak(), '- 金句收藏：' + S.favs.quote.length,
      '- 伴读收藏：' + S.favs.companion.length, '', '## 每日记录', ''];
    var keys = Object.keys(S.days).sort();
    for (var i = 0; i < keys.length; i++) {
      var k = keys[i], d = S.days[k];
      var rike = [];
      for (var r in d.rike) { if (d.rike[r] && D.rike[r]) rike.push(D.rike[r].split(' · ')[0]); }
      if (!rike.length && !d.sits.length && !d.notes.length) continue;
      lines.push('### ' + k, '', '- 日课：' + (rike.length ? rike.join('、') : '无记录'),
        '- 静坐：' + d.sits.length + ' 次 / ' + d.sits.reduce(function (a, b) { return a + (b.minutes || 0); }, 0) + ' 分钟');
      for (var n = 0; n < d.notes.length; n++) lines.push('- 省身：' + d.notes[n]);
      lines.push('');
    }
    return lines.join('\n');
  }

  function exportText(name, text, mime) {
    $('aOut').value = text;
    try {
      var blob = new Blob([text], { type: mime + ';charset=utf-8' });
      var url = URL.createObjectURL(blob);
      var a = document.createElement('a');
      a.href = url; a.download = name;
      document.body.appendChild(a); a.click(); document.body.removeChild(a);
      setTimeout(function () { URL.revokeObjectURL(url); }, 3000);
      toast('已导出，同时显示在下方文本框，可直接复制');
    } catch (e) {
      toast('已显示在下方文本框，长按可复制');
    }
  }

  function tick() {
    var now = Date.now();
    var cfg = { quote: S.settings.quoteSec, companion: S.settings.companionSec, habit: S.settings.habitSec };
    var changed = false;
    var t;
    for (t in cfg) {
      if (!S.paused[t] && now - lastRun[t] >= cfg[t] * 1000) {
        lastRun[t] = now;
        var a = list(t), cur = S.idx[t] % (a.length || 1);
        var n = cur + 1 + Math.floor(Math.random() * Math.max(1, a.length - 1));
        S.idx[t] = a.length > 1 ? n % a.length : 0;
        save();
        changed = true;
      }
    }
    if (changed && (currentPage === 'quote' || currentPage === 'companion' || currentPage === 'habit')) {
      renderPage(currentPage);
    }
    if (currentPage === 'overview') {
      $('ovNext').textContent = '金句 ' + mmss(cfg.quote - (now - lastRun.quote) / 1000) +
        ' · 伴读 ' + mmss(cfg.companion - (now - lastRun.companion) / 1000);
      $('ovUptime').textContent = Math.floor((now - bootAt) / 60000) + ' 分 ' + Math.floor((now - bootAt) / 1000 % 60) + ' 秒';
    }
    if (sitRunning) {
      sitLeft--;
      if (sitLeft <= 0) {
        sitLeft = 0; sitRunning = false;
        if (sitTimer) { clearInterval(sitTimer); sitTimer = null; }
        toast('静坐完成，记得保存本次省身');
      }
      renderSit();
    }
  }

  function bind() {
    $('themeBtn').onclick = function () {
      S.settings.theme = S.settings.theme === 'light' ? 'dark' : 'light';
      save(); applyTheme(); toast(S.settings.theme === 'light' ? '已切换日间主题' : '已切换夜间主题');
    };
    var tabs = $('tabs').getElementsByTagName('button');
    for (var i = 0; i < tabs.length; i++) {
      (function (btn) { btn.onclick = function () { show(btn.getAttribute('data-page')); }; })(tabs[i]);
    }

    $('qPrev').onclick = function () { step('quote', -1); };
    $('qNext').onclick = function () { advance('quote'); };
    $('qPause').onclick = function () { S.paused.quote = !S.paused.quote; save(); renderQuote(); };
    $('qFav').onclick = function () { toggleFav('quote'); };
    $('qSmall').onclick = function () { S.settings.fontScale = Math.max(0.8, S.settings.fontScale - 0.1); save(); renderQuote(); };
    $('qLarge').onclick = function () { S.settings.fontScale = Math.min(1.8, S.settings.fontScale + 0.1); save(); renderQuote(); };

    $('cPrev').onclick = function () { step('companion', -1); };
    $('cNext').onclick = function () { advance('companion'); };
    $('cPause').onclick = function () { S.paused.companion = !S.paused.companion; save(); renderCompanion(); };
    $('cFav').onclick = function () { toggleFav('companion'); };
    $('cGoSit').onclick = function () { show('sit'); };

    $('rList').onclick = function (e) {
      var target = e.target;
      while (target && target !== $('rList') && !target.getAttribute('data-i')) target = target.parentNode;
      if (!target || target === $('rList')) return;
      var idx = parseInt(target.getAttribute('data-i'), 10);
      var d = ensureDay(viewDate);
      d.rike[idx] = !d.rike[idx];
      save(); renderRike();
    };
    $('rPrevDay').onclick = function () { viewDate = shiftDate(viewDate, -1); renderRike(); };
    $('rNextDay').onclick = function () { if (viewDate < today()) { viewDate = shiftDate(viewDate, 1); renderRike(); } };
    $('rToday').onclick = function () { viewDate = today(); renderRike(); };
    $('rReset').onclick = function () {
      if (!window.confirm('清空 ' + viewDate + ' 的日课勾选？此操作不可撤销。')) return;
      ensureDay(viewDate).rike = {}; save(); renderRike(); toast('当日记录已清空');
    };

    $('hDone').onclick = function () { setHabitStatus('done', true); };
    $('hLater').onclick = function () { setHabitStatus('later', false); };
    $('hSkip').onclick = function () { setHabitStatus('skip', true); };
    $('hNext').onclick = function () { advance('habit'); };
    $('hPause').onclick = function () { S.paused.habit = !S.paused.habit; save(); renderHabit(); };

    var mbs = $('sMins').getElementsByTagName('button');
    for (var m = 0; m < mbs.length; m++) {
      (function (btn) {
        btn.onclick = function () {
          sitMin = parseInt(btn.getAttribute('data-min'), 10);
          sitLeft = sitMin * 60; sitRunning = false;
          if (sitTimer) { clearInterval(sitTimer); sitTimer = null; }
          for (var x = 0; x < mbs.length; x++) mbs[x].className = mbs[x] === btn ? 'primary' : '';
          renderSit();
        };
      })(mbs[m]);
    }
    $('sStart').onclick = function () {
      if (sitRunning) return;
      if (sitLeft <= 0) sitLeft = sitMin * 60;
      sitRunning = true;
      if (sitTimer) clearInterval(sitTimer);
      sitTimer = setInterval(tick, 1000);
      renderSit();
    };
    $('sPause').onclick = function () {
      sitRunning = false;
      if (sitTimer) { clearInterval(sitTimer); sitTimer = null; }
      renderSit();
    };
    $('sReset').onclick = function () {
      sitRunning = false;
      if (sitTimer) { clearInterval(sitTimer); sitTimer = null; }
      sitLeft = sitMin * 60; renderSit();
    };
    $('sSave').onclick = function () {
      var d = ensureDay(today());
      d.sits.push({
        minutes: sitMin,
        elapsed: sitMin * 60 - sitLeft,
        ts: Date.now(),
        questions: [!!$('sQ1').checked, !!$('sQ2').checked, !!$('sQ3').checked]
      });
      var note = ($('sNote').value || '').trim();
      if (note) d.notes.push(note);
      save();
      $('sNote').value = ''; $('sQ1').checked = false; $('sQ2').checked = false; $('sQ3').checked = false;
      sitLeft = sitMin * 60; sitRunning = false;
      if (sitTimer) { clearInterval(sitTimer); sitTimer = null; }
      renderSit(); toast('已保存到本机成长档案');
    };

    $('aFavs').onclick = function (e) {
      if (!e.target.getAttribute || e.target.tagName !== 'BUTTON') return;
      var type = e.target.getAttribute('data-type');
      var idx = parseInt(e.target.getAttribute('data-i'), 10);
      S.idx[type] = idx; save(); show(type);
    };
    $('aMd').onclick = function () { exportText('拙诚日课-成长档案-' + today() + '.md', buildMarkdown(), 'text/markdown'); };
    $('aJson').onclick = function () { exportText('拙诚日课-成长档案-' + today() + '.json', JSON.stringify(S, null, 2), 'application/json'); };

    window.onhashchange = function () {
      var h = (window.location.hash || '').replace('#', '');
      if (PAGES.indexOf(h) >= 0 && h !== currentPage) renderPage(h);
    };
  }

  window.ZC = { show: show, advance: advance, state: function () { return S; } };

  today();
  applyTheme();
  bind();
  var hash = (window.location.hash || '').replace('#', '');
  show(PAGES.indexOf(hash) >= 0 ? hash : 'overview');
  setInterval(tick, 1000);
})();
