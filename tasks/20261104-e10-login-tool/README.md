# E10 OA 登录工具链

| 项 | 内容 |
|---|---|
| 创建日期 | 2026-11-04 |
| 类型 | 代码 |
| 状态 | 已完成 |
| 一句话说明 | 用户级技能 e10-oa-login：装一次，OA 登录近无感（v1.3.0） |

## 目标

公司 OA（`https://oa.bgi.com`，经 IAM 跳转登录）不支持泛微 CLI 的
OIDC 代理授权（服务端报「client_id 缺失或未在认证应用中注册」）。
本任务建立 OA 登录态，供泛微流程技能使用。**泛微技能零修改**，
衔接点是泛微 CLI 自己的认证目录（本工具负责写，技能负责读）。

**关键发现（2026-11-04）**：本机存在两套泛微 CLI，认证目录不同——

| CLI | 谁在用 | 认证目录 |
|---|---|---|
| `weaver-work-cli` 0.1.40 | 市场新版技能 `weaver-e10-workflow` | `~/.weaver-work-cli/e10` |
| `e10-login` 1.6.0 | 专家插件 `weaver-e10-*` | `~/.e10-cli/profiles/` |

所以脚本是**一次登录、写全部目标**，避免"一个已登录、另一个仍提示未登录"。

## 怎么用

**方式一（推荐）· 装技能，长期近无感**
把 `dist/e10-oa-login-skill-v1.3.0/` 整个拷到 `~/.workbuddy/skills/e10-oa-login/`，
重启 WorkBuddy 生效。之后遇到登录失效/未登录，AI 会自动加载该技能：
弹浏览器 → 用户登录 → 验证 → 续跑原任务，用户无需发文件、无需说流程。

**方式二 · 发一个文件 + 一句话**
把 `dist/oa-login-v1.3.0.mjs` 发给对方，对方拖进 WorkBuddy 聊天框并说：
「运行这个脚本（后台跑）完成 OA 登录，弹出浏览器时我自己登录，成功后告诉我结果。」
成功后工作目录生成 `oa-login-state.json`（仅租户/账号/时间，不含凭据）。该文件只是本机运行记录，已加入 `.gitignore`，可删除且不影响登录。

前提：Windows + Node.js ≥ 22，系统自带 Edge 或 Chrome。
本机泛微 CLI 缺失时自动经 npx 拉取（首次约 10-20 秒）。

## 交付物

- `dist/e10-oa-login-skill-v1.3.0/` — 用户级技能包（SKILL.md + scripts/oa-login.mjs）
- `dist/oa-login-v1.3.0.mjs` — 单文件脚本（零依赖，CDP 抓会话，双 CLI 写入）
- 历史版本见 `releases/`，台账见 `VERSIONS.md`

## 目录结构

```
20261104-e10-login-tool/
├── README.md      本文件
├── VERSIONS.md    版本台账
├── skill/         技能源（SKILL.md + scripts/），即 dist 技能包的源
├── src/           oa-login.mjs 源码（单文件版）
├── prompt.txt     早期完整提示词（方式二备用）
├── dist/          当前版本交付物（入库）
└── releases/      历史版本（入库，含 v1.0.0 zip）
```

## 说明与遗留

- **2026-11-04 实测**：Edge 真实登录 28 秒完成，`status` + `whoami --live`
  双验证有效（使用默认 profile）；ETEAMSID 为 `THIRDSSO_` 前缀，印证会话由
  公司第三方 SSO（IAM）建立。Chrome 冒烟通过；v1.3.0 环境探测干跑输出
  `weaver-work-cli + e10-login(npx)` 正确。
- 技能已安装到 `~/.workbuddy/skills/e10-oa-login/`，**新会话生效**。
- 登录态过期重跑即可（约 30 秒）。
- **凭据为什么不能放工作目录**：泛微技能从 CLI 认证目录读登录态，放别处
  等于没登录；且明文 cookie 落在工作目录一旦提交即违反 `docs/SECURITY.md`。
  不含凭据的 `oa-login-state.json` 也只作本机排查记录，不入库；删除它不会注销两套 CLI。
- **共享运行环境**：`tools/e10-login/` 是本任务维护的本地 npm 环境，
  `package-lock.json` 锁定 e10-login 1.6.0；`node_modules/` 不入库，版本记录随本任务台账。
- `E10_BROWSER=edge|chrome` 强制浏览器；`OA_LOGIN_DRY=1` 只探测环境；
  第二个参数可换 OA 地址。
