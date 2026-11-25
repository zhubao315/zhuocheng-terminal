import zipfile, re, sys
apk = sys.argv[1] if len(sys.argv) > 1 else r'D:/tmp/workbuddy-data-cn/2026-11-23-09-54-19/phonebox/zhuocheng-terminal/docs/releases/zhuocheng-terminal-v2signed.apk'
z = zipfile.ZipFile(apk)
for name in ['assets/www/index.html', 'assets/www/main.js', 'assets/www/style.css']:
    s = z.read(name).decode('utf-8', 'ignore')
    print('===', name, 'len', len(s), '===')
    if name.endswith('index.html'):
        for kw in ['offline', 'wake', '电脑未连接', '唤醒电脑']:
            for m in list(re.finditer(re.escape(kw), s, re.I))[:6]:
                i = m.start()
                print(' ', kw, '@', i, ':', s[max(0, i-150):i+220].replace('\n', ' ')[:380])
    elif name.endswith('main.js'):
        for kw in ['wakeRender', '电脑未连接', '唤醒电脑', 'pcNotConnected', 'offline', 'wakeAvailable']:
            ms = list(re.finditer(re.escape(kw), s))
            print(' ', kw, 'count', len(ms), 'first', [m.start() for m in ms[:6]])
        # print context of wake-related render
        for kw in ['wakeRender', '唤醒电脑']:
            for m in list(re.finditer(re.escape(kw), s))[:2]:
                i = m.start()
                print(' CTX', kw, '@', i)
                print(s[max(0, i-400):i+700])
    else:
        for kw in ['#offline', '#wake', '电脑未连接']:
            print(' ', kw, 'count', s.count(kw))
