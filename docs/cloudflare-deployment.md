# Cloudflare 部署说明

## 当前架构

Course2Career 是 Python Streamlit 服务，不能作为普通静态网站直接部署到
Cloudflare Pages，也不能直接运行在普通 Worker Runtime 中。因此当前采用：

```text
用户
  → Cloudflare Worker
  → Streamlit Community Cloud
  → Course2Career
```

线上入口：

- Cloudflare：<https://course2career.mahongjia393.workers.dev/>
- Streamlit：<https://mhj-course2career.streamlit.app/>

## 部署内容

- Worker 名称：`course2career`
- 配置文件：`cloudflare-proxy/wrangler.jsonc`
- 代理代码：`cloudflare-proxy/worker.js`
- 可观测日志：已开启

Worker 只转发 HTTP 与 Streamlit WebSocket 流量，不保存以下内容：

- DeepSeek 或 OpenAI API Key
- 管理员用户名、密码或密码哈希
- 用户数据库
- 分析报告和课程数据

上述应用 Secrets 仍由 Streamlit Community Cloud 的 Secrets 管理。

## 更新部署

```powershell
cd cloudflare-proxy
npx wrangler deploy --minify
```

部署前应先运行：

```powershell
npx wrangler deploy --dry-run
```

## 自定义域名

当前 Cloudflare 账户还没有接入域名，因此使用 `workers.dev` 地址。
`workers.dev` 在部分网络环境中可能无法稳定访问。若需要稳定、易展示的入口：

1. 购买或准备一个自有域名。
2. 将域名添加到当前 Cloudflare 账户。
3. 在 `course2career` Worker 中添加 Custom Domain。
4. 验证首页、登录、文件上传、AI 调用和 Streamlit WebSocket。

自定义域名只替换公开入口，不改变 Streamlit 原始部署，也不需要把应用密钥
迁移到 Cloudflare。
