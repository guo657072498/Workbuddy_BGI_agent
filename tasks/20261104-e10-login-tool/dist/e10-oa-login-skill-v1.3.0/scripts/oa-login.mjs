/**
 * oa-login.mjs — 一条命令建立 BGI OA 的 AI 助手登录态（v1.3.0）
 *
 * 用法：node oa-login.mjs [OA地址]
 * 前提：Windows + Node.js >= 22（系统自带 Edge 或 Chrome）
 *
 * 做什么：弹真实浏览器 → 你正常登录 OA（IAM 跳转/扫码照旧）
 * → 抓取会话 cookie → 同时写入本机存在的泛微 CLI 认证目录：
 *     · weaver-work-cli（新版市场技能用）→ ~/.weaver-work-cli/e10
 *     · e10-login（专家插件用）        → ~/.e10-cli/profiles
 * → 自动关窗。凭据只在本地流转，不打印、不上传。
 *
 * 一套登录写两边，避免「一个 CLI 已登录、另一个还提示未登录」。
 */
import { spawn, spawnSync } from 'node:child_process';
import net from 'node:net';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';

const BASE_URL = (process.argv[2] || 'https://oa.bgi.com').replace(/\/+$/, '');
const HOSTNAME = new URL(BASE_URL).hostname;
const TIMEOUT_MS = 5 * 60 * 1000;
const POLL_MS = 2000;

function cleanEnv() {
  const env = { ...process.env };
  delete env.NODE_OPTIONS;
  return env;
}

function has(cmd, args) {
  const r = spawnSync(cmd, args, { shell: true, env: cleanEnv(), stdio: 'ignore' });
  return r.status === 0;
}

/** 检测本机可用的 CLI 写入目标（谁装写谁；e10-login 不在 PATH 时用 npx 兜底） */
function detectClients() {
  const list = [];
  if (has('weaver-work-cli', ['--version'])) {
    list.push({ name: 'weaver-work-cli', cmd: 'weaver-work-cli', prefix: ['auth', 'set'] });
  }
  if (has('e10-login', ['--version'])) {
    list.push({ name: 'e10-login', cmd: 'e10-login', prefix: ['set'] });
  } else {
    // 专家插件那套（e10-cli）没有 CLI 时也要覆盖，避免"另一套仍提示未登录"
    list.push({
      name: 'e10-login(npx)',
      cmd: process.platform === 'win32' ? 'npx.cmd' : 'npx',
      prefix: ['-y', 'e10-login@1.6.0', 'set'],
    });
  }
  return list;
}

/** 找系统已装的 Edge / Chrome（E10_BROWSER=edge|chrome 可强制指定） */
function findBrowser() {
  const pf = process.env['ProgramFiles'] || 'C:\\Program Files';
  const pf86 = process.env['ProgramFiles(x86)'] || 'C:\\Program Files (x86)';
  const lad = process.env['LOCALAPPDATA'] || '';
  const EDGE = [
    path.join(pf86, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
    path.join(pf, 'Microsoft', 'Edge', 'Application', 'msedge.exe'),
  ];
  const CHROME = [
    path.join(pf86, 'Google', 'Chrome', 'Application', 'chrome.exe'),
    path.join(pf, 'Google', 'Chrome', 'Application', 'chrome.exe'),
    path.join(lad, 'Google', 'Chrome', 'Application', 'chrome.exe'),
  ];
  const force = (process.env.E10_BROWSER || '').toLowerCase();
  const list = force === 'edge' ? EDGE : force === 'chrome' ? CHROME : [...EDGE, ...CHROME];
  return list.find((p) => p && fs.existsSync(p));
}

function freePort() {
  return new Promise((resolve, reject) => {
    const s = net.createServer();
    s.listen(0, '127.0.0.1', () => {
      const p = s.address().port;
      s.close(() => resolve(p));
    });
    s.on('error', reject);
  });
}

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

let wsSeq = 1;
function cdp(ws, method, params = {}) {
  return new Promise((resolve, reject) => {
    const id = wsSeq++;
    const onMsg = (ev) => {
      const m = JSON.parse(ev.data);
      if (m.id === id) {
        ws.removeEventListener('message', onMsg);
        m.error ? reject(new Error(m.error.message)) : resolve(m.result);
      }
    };
    ws.addEventListener('message', onMsg);
    ws.send(JSON.stringify({ id, method, params }));
  });
}

function hostMatch(domain) {
  const d = (domain || '').replace(/^\./, '').toLowerCase();
  return HOSTNAME === d || HOSTNAME.endsWith('.' + d);
}

/** 把 ETEAMSID 写入某个 CLI；返回 {ok, out} */
function runSet(target, eteamsid) {
  return new Promise((resolve) => {
    const args = [...target.prefix, '--eteamsid', eteamsid, '--base-url', BASE_URL];
    const child = spawn(target.cmd, args, {
      env: cleanEnv(),
      shell: process.platform === 'win32',
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    let out = '';
    child.stdout.on('data', (d) => { out += d; });
    child.stderr.on('data', (d) => { out += d; });
    child.on('close', (code) => resolve({ ok: code === 0, out }));
    child.on('error', () => resolve({ ok: false, out: '' }));
  });
}

async function main() {
  const browserExe = findBrowser();
  if (!browserExe) {
    console.error('[X] 未找到 Edge/Chrome，请确认系统已安装浏览器');
    process.exit(1);
  }
  const clients = detectClients();
  console.log(`写入目标：${clients.map((c) => c.name).join(' + ')}`);

  if (process.env.OA_LOGIN_DRY === '1') {
    console.log('（干跑模式：只探测环境，不打开浏览器）');
    process.exit(0);
  }

  const port = await freePort();
  const profileDir = fs.mkdtempSync(path.join(os.tmpdir(), 'oa-login-'));
  const browser = spawn(browserExe, [
    `--remote-debugging-port=${port}`,
    `--user-data-dir=${profileDir}`,
    '--no-first-run',
    '--no-default-browser-check',
    BASE_URL,
  ], { stdio: 'ignore' });

  const cleanup = async (ws) => {
    try { if (ws && ws.readyState === 1) await cdp(ws, 'Browser.close'); } catch { /* ignore */ }
    browser.kill();
    await sleep(800);
    try { fs.rmSync(profileDir, { recursive: true, force: true }); } catch { /* ignore */ }
  };

  let version = null;
  for (let i = 0; i < 20; i++) {
    try {
      const r = await fetch(`http://127.0.0.1:${port}/json/version`);
      if (r.ok) { version = await r.json(); break; }
    } catch { /* 未就绪 */ }
    if (browser.exitCode !== null) {
      console.error('[X] 浏览器启动失败');
      process.exit(1);
    }
    await sleep(500);
  }
  if (!version) {
    console.error('[X] 浏览器调试端口未就绪');
    await cleanup(null);
    process.exit(1);
  }

  const ws = new WebSocket(version.webSocketDebuggerUrl);
  await new Promise((resolve, reject) => {
    ws.addEventListener('open', resolve);
    ws.addEventListener('error', () => reject(new Error('CDP 连接失败')));
  });

  console.log('');
  console.log('请在打开的浏览器窗口中完成登录（IAM 跳转 / 扫码，一切照旧）。');
  console.log('登录成功后窗口会自动关闭，无需其他操作。');
  if (clients[0].name.endsWith('(npx)')) console.log('（本机未装泛微 CLI，首次会自动通过 npx 拉取，约 10-20 秒）');
  console.log('');

  const start = Date.now();
  let tried = false;
  let closed = false;
  browser.on('exit', () => { closed = true; });

  while (Date.now() - start < TIMEOUT_MS) {
    if (closed) {
      console.log('[X] 浏览器窗口被关闭，未完成登录');
      try { fs.rmSync(profileDir, { recursive: true, force: true }); } catch { /* ignore */ }
      process.exit(2);
    }

    let cookies = [];
    try {
      const r = await cdp(ws, 'Storage.getCookies');
      cookies = (r && r.cookies) || [];
    } catch { /* 下轮重试 */ }

    const et = cookies.filter((c) => hostMatch(c.domain)).find((c) => c.name === 'ETEAMSID' && c.value);
    if (et) {
      const results = [];
      for (const t of clients) results.push({ name: t.name, ...(await runSet(t, et.value)) });

      if (results.some((r) => r.ok)) {
        for (const r of results) {
          console.log(r.ok ? `[OK] ${r.name} 登录态已写入` : `[!] ${r.name} 写入失败（不影响已成功的目标）`);
        }
        const first = results.find((r) => r.ok);
        const pick = (k) => ((first.out.match(new RegExp(k + ':\\s*(.+)')) || [])[1] || '').trim();
        const statePath = path.join(process.cwd(), 'oa-login-state.json');
        try {
          fs.writeFileSync(statePath, JSON.stringify({
            baseUrl: BASE_URL,
            userId: pick('userId') || pick('employeeId'),
            tenantName: pick('tenantName'),
            loginAt: new Date().toISOString(),
            writtenTo: results.filter((r) => r.ok).map((r) => r.name),
            note: '本文件不含凭据；凭据在 .weaver-work-cli\\e10 与 .e10-cli\\profiles（加密）',
          }, null, 2));
        } catch { /* 写不了不影响登录 */ }
        console.log('\n[OK] 登录完成，窗口即将关闭。可以回 WorkBuddy 用了。');
        console.log(`     状态记录：${statePath}（不含凭据）`);
        await cleanup(ws);
        process.exit(0);
      }

      if (!tried) {
        tried = true;
        console.log('检测到初步会话，等你登录完成后自动校验…');
      }
    }
    await sleep(POLL_MS);
  }

  console.error('[X] 5 分钟内未完成登录，请重新运行');
  await cleanup(ws);
  process.exit(3);
}

main().catch((e) => {
  console.error('脚本异常:', e.message);
  process.exit(1);
});
