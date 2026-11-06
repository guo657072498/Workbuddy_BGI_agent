---
name: e10-oa-login
display_name: 泛微 OA 登录态助手
display_name_en: Weaver E10 OA Login Helper
description: "泛微 E10/OA 登录态建立与修复。当出现 OA 未登录、E10 登录失效、ETEAMSID 缺失或过期、e10-login 报 client_id 缺失或未在认证应用中注册、needsE10Login、login_expired、e10_login_dependency_missing、weaver-work-cli 提示 Not logged in 等情况时使用。通过本机浏览器正常登录（支持 IAM 统一认证/SSO/扫码），一次性写入本机所有泛微 CLI 的加密认证目录。"
description_zh: "泛微 E10/OA 登录态建立与修复技能。适用于 OA 未登录、登录失效、ETEAMSID 缺失、e10-login OIDC 被服务端拒绝（client_id 未在认证应用中注册）、needsE10Login、login_expired、weaver-work-cli Not logged in 等场景。调用本机 Edge/Chrome 弹出真实窗口让用户正常登录（IAM 跳转、扫码均可），自动抓取会话并写入本机全部泛微 CLI 认证目录。"
version: 1.0.0
author: 办公助理工作区
---

# 泛微 OA 登录态助手

## 适用场景（何时使用本技能）

- 泛微流程技能返回未登录、`needsE10Login`、`login_expired`、`e10_login_dependency_missing`
- `e10-login oidc` 报「参数应用标识(client_id)缺失或值未在认证应用中注册」
- `weaver-work-cli auth status` 显示 `Not logged in`
- 用户直接说「登录 OA」「OA 登录过期了」「帮我重新登录一下泛微」

## 前置条件

- Windows 10/11，Node.js ≥ 22，系统已装 Edge 或 Chrome（免下载）
- 登录脚本：`scripts/oa-login.mjs`（与本 SKILL.md 同目录下的 scripts 子目录）

## 执行步骤

**第 1 步 · 查现状**（哪个 CLI 存在就查哪个，不存在的跳过）

```bash
weaver-work-cli auth status
e10-login status
```

- 任一显示已登录且地址正确 → 直接告知用户「登录态正常，无需重新登录」，若用户原本的流程任务未完成，继续原任务。
- 两个都不存在或都未登录 → 进入第 2 步。

**第 2 步 · 运行登录脚本**（必须后台运行，最长等 5 分钟）

```bash
node "<本技能目录>/scripts/oa-login.mjs"
```

启动后**立即**告诉用户：「已弹出浏览器，请在窗口里正常登录 OA（IAM 跳转 / 扫码照旧），登录成功后窗口会自动关闭」。
脚本会自动识别本机装有哪些泛微 CLI，并**同时写入全部**（`weaver-work-cli` → `~/.weaver-work-cli/e10`，`e10-login` → `~/.e10-cli/profiles`），避免出现"一个已登录、另一个仍提示未登录"。

**第 3 步 · 验证**

```bash
weaver-work-cli auth whoami --live
e10-login whoami --live
```

把租户名、部门等**非敏感**信息报告给用户。**绝不复述 ETEAMSID 或 cookie。**

**第 4 步 · 续跑原任务**

登录成功后，若用户原本在查流程 / 发起流程 / 审批，直接继续原任务链路，不要让用户再说一遍。

## 失败处理

| 现象 | 处理 |
|---|---|
| 脚本退出码 2 | 用户关掉了浏览器窗口 → 提示"重新运行即可"，不要自动重跑 |
| 脚本退出码 3 | 5 分钟未完成登录 → 提示重新运行 |
| 提示未找到浏览器 | 让用户确认装了 Edge/Chrome |
| 写入失败 | 原文转述错误，停止；不引导用户手工复制 cookie |
| 网络/命令异常 | 如实报告并停止，不静默换方法重试 |

同一个问题最多重试一次；第二次失败即停止并报告。

## 安全与边界

- 凭据只在本地流转，加密存放在泛微 CLI 的标准认证目录，不经过任何外部服务
- 不读取、不打印、不解析凭据文件内容；验证只通过 CLI 的 `status` / `whoami`
- **不修改泛微技能包（weaver-e10-*）的任何文件**
- 本技能只负责"登录态"，不做流程业务：发起/审批等写操作仍由泛微流程技能执行，且必须经用户确认
- 换 OA 地址：`node "<技能目录>/scripts/oa-login.mjs" https://另一个OA地址`
