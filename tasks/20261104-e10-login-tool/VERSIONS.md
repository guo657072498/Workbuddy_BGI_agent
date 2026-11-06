# 版本台账 · e10-login-tool

> v1.0.0～v1.2.0 为本次统一补归档的历史版本，没有独立原始提交；后续回填的哈希表示首次入库的归档提交，不冒充原始发布提交。

| 版本 | 日期 | 交付物 | 变更摘要 | 提交 |
|---|---|---|---|---|
| v1.0.0 | 2026-11-04 | dist/e10-login-tool-v1.0.0.zip | 首版复用包：零依赖登录脚本（CDP 读 cookie）+ 双击入口 + 内置 e10-login@1.6.0（win-x64 原样打包），支持 Edge/Chrome（E10_BROWSER 可强制指定）。同事解压双击 login-oa.bat，正常登录 OA 约 30 秒即建立 AI 助手登录态 | 待提交 |
| v1.1.0 | 2026-11-04 | dist/oa-login-v1.1.0.mjs + dist/oa-login-prompt-v1.1.0.txt | 交接形态简化为「一个文件 / 一段提示词」：去掉内置依赖包、bat 与 zip，e10-login 未安装时自动经 npx 拉取。不兼容：v1.0.0 的 zip 不再维护（已归档 releases/） | 待提交 |
| v1.2.0 | 2026-11-04 | dist/oa-login-v1.2.0.mjs + dist/oa-login-init-v1.2.0.txt + dist/oa-login-prompt-v1.2.0.txt | 新增「方式一初始化话术」；登录成功后在当前工作目录生成 oa-login-state.json 状态记录（仅租户/账号/登录时间，不含凭据）。凭据仍加密存 ~/.e10-cli，因为泛微技能从该路径读取 | 待提交 |
| v1.3.0 | 2026-11-04 | dist/e10-oa-login-skill-v1.3.0/ + dist/oa-login-v1.3.0.mjs | 封装为用户级技能（SKILL.md + scripts），同事装一次即近无感；脚本升级为**一次登录同时写两个 CLI**（weaver-work-cli → ~/.weaver-work-cli/e10；e10-login → ~/.e10-cli/profiles，不在 PATH 时用 npx），解决"一新一旧两套认证互不相通"；新增 OA_LOGIN_DRY 环境探测 | 待提交 |
