/**
 * oa-login.mjs — 一条命令建立 BGI OA 的 AI 助手登录态
 *
 * 用法：node oa-login.mjs
 * 前提：Windows + Node.js >= 22（系统自带 Edge 或 Chrome）
 *
 * 做什么：弹一个真实浏览器窗口 → 你正常登录 OA（IAM 跳转照旧）
 * → 脚本抓取会话 cookie → 写入 e10-cli 认证文件 → 自动关窗。
 * 凭据只在本地流转，不打印、不上传。
 *
 * e10-login 来源：优先用 PATH 里已装的；没有就通过 npx 临时拉取（首次约 10-20 秒）。
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

/** e10-login 从哪来：PATH 优先，否则 npx 临时拉取 */
function resolveE10() {
  const probe = spawnSync('e10-login', ['--version'], { shell: true, env: cleanEnv() });
  return probe.status === 0 ? 'path' : 'npx';
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

function runSet(eteamsid, source) {
  return new Promise((resolve) => {
    const base = ['set', '--eteamsid', eteamsid, '--base-url', BASE_URL];
    const cmd = source === 'path' ? 'e10-login' : (process.platform === 'win32' ? 'npx.cmd' : 'npx');
    const args = source === 'path' ? base : ['-y', 'e10-login@1.6.0', ...base];
    const child = spawn(cmd, args, {
      env: cleanEnv(),
      shell: process.platform === 'win32',
      stdio: ['ignore', 'pipe', 'pipe'],
    });
    let out = '';
    child.stdout.on('data', (d) => { out += d; });
    child.stderr.on('data', (d) => { out += d; });
    child.on('close', (code) => resolve({ code, out }));
    child.on('error', () => resolve({ code: 1, out: '' }));
  });
}

async function main() {
  const browserExe = findBrowser();
  if (!browserExe) {
    console.error('[X] 未找到 Edge/Chrome，请确认系统已安装浏览器');
    process.exit(1);
  }
  const e10 = resolveE10();

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
  if (e10 === 'npx') console.log('（本机未装 e10-login，首次会自动通过 npx 拉取，约 10-20 秒）');
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
      const { code, out } = await runSet(et.value, e10);
      if (code === 0) {
        console.log(out.trim());
        console.log('\n[OK] 登录态已保存，窗口即将关闭。可以回 WorkBuddy 用了。');
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
