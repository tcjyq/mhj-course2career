# 部署说明

## 当前定位

当前版本适合本地运行、作品集演示和受控测试。开放系统 AI 能力前，应先完成限流、真实 Token/费用统计、权限会话失效和全局预算熔断。

## 环境配置

从 `.env.example` 复制本地配置，不要提交 `.env`。生产环境应通过部署平台的 Secret 管理功能设置：

- `OPENAI_API_KEY`
- `DEEPSEEK_API_KEY`
- `COURSE2CAREER_KEY_ENCRYPTION_KEY`
- `COURSE2CAREER_DATABASE_PATH`
- `COURSE2CAREER_BOOTSTRAP_ADMIN_USERNAME`
- `COURSE2CAREER_BOOTSTRAP_ADMIN_PASSWORD`

只使用本地规则模式时，模型凭证和加密主密钥可以留空。

## 创建首个管理员

项目不会提供通用默认管理员，也不会把管理员密码写进仓库。部署到 Streamlit Community Cloud 后，在应用的 **Settings → Secrets** 中设置：

```toml
COURSE2CAREER_BOOTSTRAP_ADMIN_USERNAME = "自行设置的管理员用户名"
COURSE2CAREER_BOOTSTRAP_ADMIN_PASSWORD = "至少12位的独立强密码"
```

保存后应用会重新启动，并创建 `Admin` 套餐的管理员。随后从“登录”页面使用这组凭证登录，左侧会出现“管理员Dashboard”。

初始化是幂等的：管理员已经存在时不会重置密码。如果配置的用户名已被普通账户占用，应用会拒绝自动提权并提示更换用户名。

Streamlit Community Cloud 的本地 SQLite 文件不保证永久保存。保留这两项 Secrets，可以在运行环境重建后重新创建管理员。不要把真实密码提交到 `.env.example`、GitHub Issue、日志或聊天记录。

## 启动

```powershell
python -m pip install -r requirements.txt
streamlit run app.py
```

## 发布前检查

1. 测试、Ruff 和格式检查全部通过。
2. 仓库中不存在 `.env`、数据库、日志、缓存或真实凭证。
3. 使用 HTTPS，并在反向代理层设置请求速率、并发和上传大小限制。
4. 备份数据库与 API Key 加密主密钥，但两者分开保存。
5. 不把用户课程、完整 JD、密码或 API Key 写入日志。
6. 公开页面提供隐私说明和第三方模型数据传输提示。
