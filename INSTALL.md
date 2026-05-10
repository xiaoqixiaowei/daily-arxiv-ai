# daily-arxiv-ai 安装部署说明

这份文档用于把 `daily-arxiv-ai` 部署成一个每天自动更新的 arXiv 论文阅读站点。

当前推荐架构：

```text
GitHub private repo
  -> GitHub Actions 每天抓取 arXiv + 调用 LLM 总结 + 写入 data/
  -> Cloudflare Pages 部署静态站点
  -> Cloudflare Access 限制访问
```

## 1. GitHub 仓库准备

仓库地址：

```text
https://github.com/<你的 GitHub 用户名>/<你的仓库名>
```

仓库可以保持 private，不需要开启 GitHub Pages。

进入仓库后，先确认 Actions 有写入权限：

```text
Settings
  -> Actions
  -> General
  -> Workflow permissions
  -> Read and write permissions
  -> Save
```

不要特意开启 `Fork pull request workflows`，它和本项目的定时任务无关。

## 2. GitHub Secrets

进入：

```text
Settings
  -> Secrets and variables
  -> Actions
  -> Secrets
  -> New repository secret
```

添加两个 Secrets。

```text
Name: OPENAI_API_KEY
Secret: 你的真实 API key
```

```text
Name: OPENAI_BASE_URL
Secret: https://models.sjtu.edu.cn/api/v1
```

注意：

- `OPENAI_API_KEY` 只粘贴 key 本身，不要写 `OPENAI_API_KEY=`。
- `OPENAI_BASE_URL` 不要加 `/chat/completions`。
- `/chat/completions` 会由 OpenAI-compatible SDK 自动拼接。

## 3. GitHub Variables

进入：

```text
Settings
  -> Secrets and variables
  -> Actions
  -> Variables
  -> New repository variable
```

添加这些 Variables：

```text
Name: CATEGORIES
Value: cs.CV,cs.CL,cs.AI,cs.GR,cs.LG
```

```text
Name: INCLUDE_KEYWORDS
Value: vision-language model,vision language model,vlm,multimodal large language model,mllm,video-language model,world model,world models,world modeling,video world model,generative world model,action-conditioned world model,embodied world model,game agent,game agents,game-playing agent,game playing agent,multimodal game agent,autonomous game agent,llm game agent,vlm game agent,game ai,game environment,game environments,game benchmark,game benchmarks,gameplay reasoning,gameplay understanding,minecraft benchmark,minecraft agent
```

```text
Name: LANGUAGE
Value: Chinese
```

```text
Name: MODEL_NAME
Value: glm-5.1
```

```text
Name: LLM_REQUEST_INTERVAL_SECONDS
Value: 6.5
```

```text
Name: EMAIL
Value: <你的 GitHub noreply 邮箱>
```

```text
Name: NAME
Value: <你的 GitHub 用户名>
```

`EMAIL` 推荐使用 GitHub noreply 邮箱，格式通常类似：

```text
<你的 GitHub 用户 ID>+<你的 GitHub 用户名>@users.noreply.github.com
```

模型调用名参考：

```text
DeepSeek V3.2 常规模式: deepseek-chat
DeepSeek V3.2 思考模式: deepseek-reasoner
MiniMax-M2.7: minimax 或 minimax-m2.7
GLM-5.1: glm 或 glm-5.1
Qwen3.5-27B: qwen 或 qwen3.5-27b
```

当前使用：

```text
MODEL_NAME=glm-5.1
```

推荐主题配置面向游戏 agent 相关论文：

```text
CATEGORIES=cs.CV,cs.CL,cs.AI,cs.GR,cs.LG
```

这些类别覆盖：

```text
cs.CV: 视觉游戏环境、视觉交互、视觉 agent
cs.CL: 语言驱动 agent、游戏文本环境
cs.AI: 游戏 AI、智能体、规划
cs.GR: 图形学、游戏、仿真
cs.LG: 强化学习、agent 学习方法
```

`INCLUDE_KEYWORDS` 会在标题、摘要和分类里做二次过滤，只保留命中关键词的论文。想看更多就删掉一些限制，想更窄就减少关键词。

平台限制：

```text
每分钟请求数: 10
每分钟 token 消耗: 100000
每周 token 总量: 1000000000
```

所以 `LLM_REQUEST_INTERVAL_SECONDS=6.5` 用来限制 LLM 调用频率，避免超过 10 requests/min。

## 4. 手动运行 GitHub Actions

进入：

```text
Actions
  -> arXiv-daily-ai-enhanced
  -> Run workflow
  -> Branch: main
  -> Run workflow
```

运行详情页里会看到一个 workflow run，例如：

```text
arXiv-daily-ai-enhanced #1
Status: Queued
Job: build
```

`Queued` 表示任务已经触发，正在等待 GitHub runner。稍等后会变成 running。

重点检查这些步骤：

```text
Install dependencies
Crawl arXiv papers
Check for duplicates
AI Enhancement Processing
Convert to Markdown
Update file list
Commit code changes to main branch
Push code changes to main branch
```

成功后，`main` 分支会出现或更新：

```text
data/*.jsonl
data/*.md
assets/file-list.txt
```

## 5. Cloudflare Pages 部署

进入 Cloudflare：

```text
Workers & Pages
  -> Create application
  -> Pages
  -> Connect to Git
  -> 选择你的 GitHub 仓库
```

构建设置：

```text
Framework preset: None
Build command: bash scripts/cloudflare-build.sh
Build output directory: dist
Root directory: 留空
```

如果你创建的是 Workers 项目，并且 Cloudflare 后台显示的是 Deploy command，请使用：

```text
bash scripts/cloudflare-deploy.sh
```

这个脚本会先生成 `dist`，再执行：

```text
npx wrangler versions upload --config wrangler.jsonc --assets=./dist
```

本仓库已经包含：

```text
wrangler.jsonc
scripts/cloudflare-build.sh
scripts/cloudflare-deploy.sh
```

如果 Cloudflare 使用 `npx wrangler deploy`，也可以正常部署，因为 `wrangler.jsonc` 已经指定静态资源目录为 `dist`。

不要使用 Jekyll 构建。如果看到类似下面的错误，说明 Cloudflare 误判了构建方式：

```text
npx bundle exec jekyll build
npm error could not determine executable to run
```

解决方式就是确认 Cloudflare 的 Build command 是：

```text
bash scripts/cloudflare-build.sh
```

并且 Output directory 是：

```text
dist
```

## 6. Cloudflare Access 访问控制

如果不想别人直接看页面，不要把 GitHub 仓库改 public，也不要用 GitHub Pages。

使用 Cloudflare Access：

```text
Cloudflare Zero Trust
  -> Access
  -> Applications
  -> Add an application
  -> Self-hosted
```

配置：

```text
Application domain: 你的 Cloudflare Pages 域名
Policy: Allow
Include: 你的邮箱
```

这样别人访问站点时，会先被 Cloudflare 登录拦住。

## 7. 常见问题

### Actions 一直 Queued

通常是 GitHub runner 排队，等几分钟即可。

如果长期不动，检查：

```text
Settings -> Actions -> General
```

确认 Actions 没有被禁用。

### AI Enhancement Processing 失败

优先检查：

```text
OPENAI_API_KEY 是否正确
OPENAI_BASE_URL 是否为 https://models.sjtu.edu.cn/api/v1
MODEL_NAME 是否为 glm-5.1
```

如果日志里出现限流，调大：

```text
LLM_REQUEST_INTERVAL_SECONDS=7
```

### Cloudflare 构建失败

如果日志里出现：

```text
Missing entry-point to Worker script or to assets directory
```

说明 Cloudflare 的部署命令没有指定 Worker 入口或静态资源目录。Workers 项目请确认：

```text
Deploy command: bash scripts/cloudflare-deploy.sh
```

Pages 项目请确认：

```text
Build command: bash scripts/cloudflare-build.sh
Build output directory: dist
```

### 页面能打开但没有数据

先确认 GitHub Actions 已成功生成：

```text
data/
assets/file-list.txt
```

然后重新部署 Cloudflare Pages。

## 8. 日常使用

正常情况下不需要手动操作。

GitHub Actions 会每天北京时间 09:30 自动运行：

```text
cron: 30 1 * * *
```

它对应 UTC 01:30，也就是北京时间 09:30。

如果想立即更新，进入 Actions 手动点 `Run workflow` 即可。
