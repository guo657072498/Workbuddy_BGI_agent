# 办公助理 (Office Assistant)

基于 WorkBuddy 的办公自动化项目工作区。本仓库用于对项目文件做版本管理。

## 目录说明

| 路径 | 说明 |
| --- | --- |
| `.workbuddy/memory/` | 项目工作日志与长期笔记（可追溯的上下文沉淀） |
| `.workbuddy/skills/` | 项目级技能（若有） |

## Git 使用约定

- 主分支：`main`
- 远程仓库：`origin` → https://github.com/guo657072498/Workbuddy_BGI_agent
- 提交前请确认 `.env`、密钥、凭据等敏感文件未被纳入版本控制（见 `.gitignore`）

### 常用命令

```bash
git status                 # 查看改动
git add -A                 # 暂存全部改动
git commit -m "说明"       # 提交
git push origin main       # 推送
```

## 敏感信息

仓库为私有，但仍严禁提交以下内容：

- `.env` / `.env.*`、`*.pem`、`*.key`
- `secrets.json`、`credentials.json`、`token.json`
- 任何第三方平台的访问令牌
