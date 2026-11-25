/* 拙诚日课终端 · 全离线版 2.0
   所有内容来自内嵌 DATA，所有状态存于 localStorage。
   不访问网络、不调用 API、不依赖电脑端。兼容 Chromium 80 级 WebView。 */
(function () {
  'use strict';

  var KEY = 'zhuocheng.offline.v2';
  var D = window.ZC_DATA || { quotes: [], companions: [], microhabits: [], rike: [], reminders: [] };
  var PAGES = ['overview', 'quote', 'companion', 'rike', 'habit', 'sit', 'archive'];
  var SCREEN_MODULES = [
    { key: 'quote', label: '每日金句' },
    { key: 'companion', label: 'AI 伴读' },
    { key: 'rike', label: '日课十二条' },
    { key: 'habit', label: '微习惯' },
    { key: 'sit', label: '静坐三省' },
    { key: 'archive', label: '成长档案' }
  ];
  var ALL_MODULES = ['quote', 'companion', 'rike', 'habit', 'sit', 'archive'];
  // 多端预设：留白用于避开固定系统栏/外壳区域；scale 控制信息屏字号
  var PROFILES = {
    'note2-landscape': { safeTop: 0, safeBottom: 0, scale: 1.45, sec: 20 },
    'note2-portrait': { safeTop: 0, safeBottom: 0, scale: 1.15, sec: 18 },
    'tablet': { safeTop: 12, safeBottom: 12, scale: 1.25, sec: 20 },
    'desktop': { safeTop: 0, safeBottom: 0, scale: 1.1, sec: 25 }
  };
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
      settings: {
        theme: 'dark', fontScale: 1, quoteSec: 180, companionSec: 600, habitSec: 3600,
        mode: 'screen', profile: 'auto', safeTop: 0, safeBottom: 0,
        screenScale: 1.45, screenSec: 20, screenModules: ALL_MODULES.slice()
      },
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
    if (s.settings.mode !== 'full') s.settings.mode = 'screen';
    if (!PROFILES[s.settings.profile] && s.settings.profile !== 'auto') s.settings.profile = 'auto';
    if (!s.settings.screenModules || !s.settings.screenModules.length) s.settings.screenModules = ALL_MODULES.slice();
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
    document.body.className = (light ? 'light ' : '') + (S.settings.mode === 'screen' ? 'screen-mode' : '');
    if ($('themeBtn')) $('themeBtn').textContent = light ? '夜间' : '日间';
  }

  /* ---------------- 信息屏（默认形态，极少互动） ---------------- */

  var screenOrder = ALL_MODULES.slice();
  var screenAt = 0, screenElapsed = 0, screenPaused = false;
  var hintTimer = null, suppressClick = false, swiped = false, longTimer = null;
  var touchX = 0, touchY = 0, tapCount = 0, singleTimer = null;

  function currentProfile() {
    var p = S.settings.profile;
    if (p === 'auto') return window.innerWidth >= window.innerHeight ? 'note2-landscape' : 'note2-portrait';
    return PROFILES[p] ? p : 'note2-landscape';
  }

  function applyScreenConfig() {
    var st = S.settings;
    var p = PROFILES[currentProfile()];
    if (st.profile === 'auto' && !st.autoTuned) {
      st.safeTop = p.safeTop; st.safeBottom = p.safeBottom;
      st.screenScale = p.scale; st.screenSec = p.sec;
    }
    var root = document.documentElement;
    root.style.setProperty('--safe-top', Math.max(0, st.safeTop) + 'px');
    root.style.setProperty('--safe-bottom', Math.max(0, st.safeBottom) + 'px');
    root.style.setProperty('--screen-scale', String(st.screenScale));
    applyTheme();
    var order = [];
    for (var i = 0; i < ALL_MODULES.length; i++) {
      if (st.screenModules.indexOf(ALL_MODULES[i]) >= 0) order.push(ALL_MODULES[i]);
    }
    screenOrder = order.length ? order : ALL_MODULES.slice();
    if (screenAt >= screenOrder.length) screenAt = 0;
    if (st.mode === 'screen') renderScreen();
  }

  function showHint() {
    var h = $('scHint');
    if (!h) return;
    h.className = 'screen-hint';
    if (hintTimer) clearTimeout(hintTimer);
    hintTimer = setTimeout(function () { h.className = 'screen-hint dim'; }, 6000);
  }

  function screenHtml(key) {
    var now = new Date();
    var q, h, c, d, i, n;
    if (key === 'quote') {
      q = current('quote');
      return '<div class="sc-quote"><span class="sc-kicker">今日金句 · ' + (S.idx.quote + 1) + ' / ' +
        D.quotes.length + '</span><blockquote>' + esc(q.text || '—') + '</blockquote>' +
        '<div class="sc-source">' + esc(q.source || '—') + (q.tag ? ' · ' + esc(q.tag) : '') + '</div></div>';
    }
    if (key === 'companion') {
      c = current('companion');
      return '<div class="sc-companion"><span class="sc-kicker">AI 伴读 · ' + (S.idx.companion + 1) + ' / ' +
        D.companions.length + '</span><p class="sc-passage">' + esc(c.passage || '—') + '</p>' +
        '<div class="sc-source">' + esc(c.source || '—') + '</div>' +
        '<p class="sc-insight">' + esc(c.insight || '') + '</p>' +
        '<div class="sc-question">今日一问 · ' + esc(c.question || '') + '</div></div>';
    }
    if (key === 'rike') {
      d = ensureDay(today());
      n = rikeDone(today());
      var grid = '';
      for (i = 0; i < D.rike.length; i++) {
        grid += '<div class="sc-item' + (d.rike[i] ? ' done' : '') + '"><span class="tick">' +
          (d.rike[i] ? '✓' : '') + '</span>' + esc(D.rike[i]) + '</div>';
      }
      return '<div class="sc-rike"><span class="sc-kicker">曾国藩日课十二条 · 今日 ' + n + ' / ' +
        D.rike.length + '</span><div class="sc-grid">' + grid + '</div></div>';
    }
    if (key === 'habit') {
      h = current('habit'); d = ensureDay(today());
      var doneHabit = 0;
      for (var hk in d.habits) { if (d.habits[hk] === 'done') doneHabit++; }
      return '<div class="sc-habit"><span class="sc-kicker">微习惯 · 此刻行动</span>' +
        '<div class="sc-action">' + esc(h.habit || '—') + '</div><div class="sc-chips">' +
        '<span>对应日课 · ' + esc(h.maps || '—') + '</span><span>' + (h.duration_minutes || 2) + ' 分钟</span>' +
        '<span>今日完成 ' + doneHabit + '</span></div></div>';
    }
    if (key === 'sit') {
      d = ensureDay(today());
      return '<div class="sc-sit"><span class="sc-kicker">静坐三省 · 回到自己</span>' +
        '<div class="breath running"><span>静</span></div>' +
        '<p class="sc-hintline">今日已静坐 ' + d.sits.length + ' 次 · 调匀呼吸，走神了轻轻回来</p></div>';
    }
    if (key === 'archive') {
      var days = activeDays(), sits = 0, minutes = 0, habits = 0;
      for (i = 0; i < days.length; i++) {
        d = S.days[days[i]];
        sits += d.sits.length;
        for (var j = 0; j < d.sits.length; j++) minutes += (d.sits[j].minutes || 0);
        for (var hb in d.habits) { if (d.habits[hb] === 'done') habits++; }
      }
      var week = '';
      for (var b = 6; b >= 0; b--) {
        var dk = shiftDate(today(), -b);
        var dn = rikeDone(dk);
        var pct = Math.round(dn / (D.rike.length || 12) * 100);
        week += '<div class="week-row"><span>' + dk.slice(5) + '</span><div class="week-bar"><i style="width:' +
          pct + '%"></i></div><b>' + dn + '/' + D.rike.length + '</b></div>';
      }
      return '<div class="sc-archive"><span class="sc-kicker">成长档案 · 全部留在本机</span>' +
        '<div class="sc-stats"><div class="sc-stat"><small>连续天数</small><b>' + streak() + '</b></div>' +
        '<div class="sc-stat"><small>有记录天数</small><b>' + days.length + '</b></div>' +
        '<div class="sc-stat"><small>微习惯完成</small><b>' + habits + '</b></div>' +
        '<div class="sc-stat"><small>静坐次 / 分</small><b>' + sits + ' / ' + minutes + '</b></div></div>' +
        '<div class="sc-week">' + week + '</div></div>';
    }
    return '<div class="sc-quote"><blockquote>拙诚日课终端</blockquote></div>';
  }

  function renderScreen() {
    if (!screenOrder.length) screenOrder = ALL_MODULES.slice();
    if (screenAt >= screenOrder.length) screenAt = 0;
    var now = new Date();
    $('scDate').textContent = now.getFullYear() + ' 年 ' + (now.getMonth() + 1) + ' 月 ' + now.getDate() +
      ' 日 · 星期' + weekText(now);
    $('scClock').textContent = pad(now.getHours()) + ':' + pad(now.getMinutes()) + ':' + pad(now.getSeconds()) +
      (screenPaused ? ' · 已暂停' : '');
    $('scBody').innerHTML = screenHtml(screenOrder[screenAt]);
    $('scProgress').style.width = Math.round(screenElapsed / Math.max(1, S.settings.screenSec) * 100) + '%';
  }

  function screenStep(delta) {
    if (!screenOrder.length) return;
    screenAt = (screenAt + delta + screenOrder.length) % screenOrder.length;
    screenElapsed = 0;
    renderScreen();
    showHint();
  }

  function screenTick() {
    if (S.settings.mode !== 'screen') return;
    var now = new Date();
    $('scClock').textContent = pad(now.getHours()) + ':' + pad(now.getMinutes()) + ':' + pad(now.getSeconds()) +
      (screenPaused ? ' · 已暂停' : '');
    if (screenPaused) return;
    screenElapsed++;
    if (screenElapsed >= Math.max(5, S.settings.screenSec)) { screenStep(1); }
    else $('scProgress').style.width = Math.round(screenElapsed / Math.max(5, S.settings.screenSec) * 100) + '%';
  }

  function openConfig() {
    var st = S.settings;
    $('cfgTop').value = st.safeTop;
    $('cfgBottom').value = st.safeBottom;
    $('cfgScale').value = st.screenScale;
    $('cfgSec').value = st.screenSec;
    $('cfgTheme').value = st.theme;
    $('cfgMode').value = st.mode;
    var ps = $('cfgProfiles').getElementsByTagName('button');
    for (var i = 0; i < ps.length; i++) {
      ps[i].className = ps[i].getAttribute('data-profile') === st.profile ? 'active' : '';
    }
    var mh = '';
    for (var m = 0; m < SCREEN_MODULES.length; m++) {
      var sm = SCREEN_MODULES[m];
      mh += '<label><input type="checkbox" data-key="' + sm.key + '"' +
        (st.screenModules.indexOf(sm.key) >= 0 ? ' checked' : '') + '>' + sm.label + '</label>';
    }
    $('cfgModules').innerHTML = mh;
    $('cfgMask').hidden = false;
    $('cfgPanel').hidden = false;
    screenPaused = true;
    suppressClick = true;
  }

  function closeConfig() {
    $('cfgMask').hidden = true;
    $('cfgPanel').hidden = true;
    screenPaused = false;
    screenElapsed = 0;
    suppressClick = true;
    renderScreen();
  }

  function readConfigForm() {
    var st = S.settings;
    var active = $('cfgProfiles').querySelector('button.active');
    var boxes = $('cfgModules').getElementsByTagName('input');
    var mods = [];
    for (var i = 0; i < boxes.length; i++) { if (boxes[i].checked) mods.push(boxes[i].getAttribute('data-key')); }
    st.profile = active ? active.getAttribute('data-profile') : 'auto';
    st.safeTop = Math.min(240, Math.max(0, parseInt($('cfgTop').value, 10) || 0));
    st.safeBottom = Math.min(240, Math.max(0, parseInt($('cfgBottom').value, 10) || 0));
    st.screenScale = Math.min(1.8, Math.max(0.8, parseFloat($('cfgScale').value) || 1));
    st.screenSec = Math.min(300, Math.max(5, parseInt($('cfgSec').value, 10) || 20));
    st.theme = $('cfgTheme').value;
    st.mode = $('cfgMode').value;
    st.screenModules = mods.length ? mods : ALL_MODULES.slice();
    st.autoTuned = true;
  }

  function saveConfig() {
    readConfigForm();
    save();
    closeConfig();
    applyScreenConfig();
    renderScreen();
    toast('配置已保存到本机');
  }

  function resetConfig() {
    var d = defaults();
    for (var k in d.settings) { S.settings[k] = d.settings[k]; }
    save();
    openConfig();
    applyScreenConfig();
    toast('已恢复默认配置');
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
    // 信息屏：轻触换屏、双击暂停、长按配置、左右滑动换屏
    var sc = $('screen');
    sc.addEventListener('touchstart', function (e) {
      var t = e.touches[0];
      touchX = t.clientX; touchY = t.clientY; swiped = false;
      if (longTimer) clearTimeout(longTimer);
      longTimer = setTimeout(function () { longTimer = null; openConfig(); }, 650);
    }, { passive: true });
    sc.addEventListener('touchmove', function (e) {
      var t = e.touches[0];
      if (Math.abs(t.clientX - touchX) > 40 || Math.abs(t.clientY - touchY) > 40) {
        swiped = true;
        if (longTimer) { clearTimeout(longTimer); longTimer = null; }
      }
    }, { passive: true });
    sc.addEventListener('touchend', function (e) {
      if (longTimer) { clearTimeout(longTimer); longTimer = null; }
      if (swiped) {
        var t = e.changedTouches[0];
        if (Math.abs(t.clientX - touchX) > Math.abs(t.clientY - touchY)) screenStep(t.clientX < touchX ? 1 : -1);
        suppressClick = true;
      }
    }, { passive: true });
    sc.addEventListener('click', function () {
      if (suppressClick) { suppressClick = false; return; }
      tapCount++;
      if (tapCount === 1) {
        singleTimer = setTimeout(function () { screenStep(1); tapCount = 0; singleTimer = null; }, 320);
      } else if (tapCount === 2) {
        if (singleTimer) { clearTimeout(singleTimer); singleTimer = null; }
        screenPaused = !screenPaused;
        renderScreen();
        toast(screenPaused ? '轮播已暂停' : '轮播已继续');
        tapCount = 0;
      }
    });

    $('cfgBtn').onclick = openConfig;
    $('cfgClose').onclick = closeConfig;
    $('cfgMask').onclick = closeConfig;
    $('cfgSave').onclick = saveConfig;
    $('cfgReset').onclick = resetConfig;
    var pbs = $('cfgProfiles').getElementsByTagName('button');
    for (var pi = 0; pi < pbs.length; pi++) {
      (function (btn) {
        btn.onclick = function () {
          var p = PROFILES[btn.getAttribute('data-profile')];
          if (!p) return;
          for (var x = 0; x < pbs.length; x++) pbs[x].className = '';
          btn.className = 'active';
          $('cfgTop').value = p.safeTop;
          $('cfgBottom').value = p.safeBottom;
          $('cfgScale').value = p.scale;
          $('cfgSec').value = p.sec;
        };
      })(pbs[pi]);
    }

    document.addEventListener('keydown', function (e) {
      if (S.settings.mode !== 'screen' || !$('cfgPanel').hidden) return;
      if (e.key === 'ArrowRight' || e.key === 'PageDown') { screenStep(1); e.preventDefault(); }
      else if (e.key === 'ArrowLeft' || e.key === 'PageUp') { screenStep(-1); e.preventDefault(); }
      else if (e.key === ' ' || e.key === 'Enter') {
        screenPaused = !screenPaused; renderScreen(); e.preventDefault();
      } else if (e.key === 'c' || e.key === 'C') { openConfig(); }
    });

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

  window.ZC = {
    show: show, advance: advance, state: function () { return S; },
    screenNext: function () { screenStep(1); },
    screenPrev: function () { screenStep(-1); },
    screenMode: function (on) {
      S.settings.mode = on ? 'screen' : 'full'; save(); applyScreenConfig(); renderScreen();
    },
    setConfig: function (patch) {
      for (var k in patch) { if (Object.prototype.hasOwnProperty.call(patch, k)) S.settings[k] = patch[k]; }
      save(); applyScreenConfig(); renderScreen();
    },
    config: function () {
      return {
        profile: currentProfile(), mode: S.settings.mode, safeTop: S.settings.safeTop,
        safeBottom: S.settings.safeBottom, scale: S.settings.screenScale, sec: S.settings.screenSec,
        order: screenOrder.slice(), at: screenAt, paused: screenPaused
      };
    },
    openConfig: openConfig, closeConfig: closeConfig
  };

  today();
  try {
    var qs = window.location.search || '';
    var pm = /[?&]profile=([^&]+)/.exec(qs);
    var md = /[?&]mode=([^&]+)/.exec(qs);
    if (pm && PROFILES[pm[1]]) S.settings.profile = pm[1];
    if (md && (md[1] === 'screen' || md[1] === 'full')) S.settings.mode = md[1];
  } catch (e) { /* file:// 下忽略 */ }
  applyScreenConfig();
  bind();
  var hash = (window.location.hash || '').replace('#', '');
  show(PAGES.indexOf(hash) >= 0 ? hash : 'overview');
  renderScreen();
  showHint();
  setInterval(tick, 1000);
  setInterval(screenTick, 1000);
})();
