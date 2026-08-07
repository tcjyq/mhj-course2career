# 部署说明

## 当前定位

当前版本适合本地运行、作品集演示和受控测试。开放系统 AI 能力前，应先完成限流、真实 Token/费用统计、权限会话失效和全局预算熔断。

## 环境配置

从 `.env.example` 复制本地配置，不要提交 `.env`。生产环境应通过部署平台的 Secret 管理功能设置：

- `OPENAI_API_KEY`
- `DEEPSEEK_API_KEY`
- `DEEPSEEK_MODEL` / `DEEPSEEK_MODEL_MODE` / `DEEPSEEK_MODEL_PREFERENCE`
- `DEEPSEEK_MODEL_CACHE_SECONDS` / `DEEPSEEK_MODEL_STALE_SECONDS`
- `DEEPSEEK_MAX_OUTPUT_TOKENS` / `SYSTEM_AI_ENABLED`
- `OPENAI_INPUT_COST_PER_MILLION` / `OPENAI_OUTPUT_COST_PER_MILLION`
- `DEEPSEEK_INPUT_COST_PER_MILLION` / `DEEPSEEK_OUTPUT_COST_PER_MILLION`
- `COURSE2CAREER_KEY_ENCRYPTION_KEY`
- `COURSE2CAREER_DATABASE_PATH`
- `ADMIN_USERNAME`
- `ADMIN_PASSWORD` 或 `ADMIN_PASSWORD_HASH`（二选一）

模型单价按每百万Token填写，多个供应商必须先换算成同一币种。若暂时无法确认
当前价格，保持`0`：系统仍会记录真实输入/输出Token，但不会生成可能过时的
费用估算。

只使用本地规则模式时，模型凭证和加密主密钥可以留空。

`DEEPSEEK_MODEL_MODE=auto_safe`是默认方案：应用读取官方模型目录，但只在代码白名单和配置优先级内选择。若需要完全固定行为，可设置`pinned`。紧急情况下将`SYSTEM_AI_ENABLED=false`，系统AI会停止，规则模式仍可使用。

如需启用 GitHub 的每日模型目录监测，在仓库 **Settings → Secrets and variables → Actions** 中单独创建`DEEPSEEK_API_KEY`。工作流只读取模型目录，发现未知模型时创建 Issue；Secret 不会写入日志或仓库。未配置该 Secret 时工作流安全跳过。

## 创建首个管理员

项目不会提供通用默认管理员，也不会把管理员密码写进仓库。生产环境推荐先生成 scrypt 哈希：

```powershell
python -c "from getpass import getpass; from course2career.password_security import hash_password; print(hash_password(getpass('Admin password: ')))"
```

命令通过隐藏输入读取密码，不会把密码写进命令历史。部署到 Streamlit Community Cloud 后，在应用的 **Settings → Secrets** 中设置用户名和生成的哈希：

```toml
ADMIN_USERNAME = "自行设置的管理员用户名"
ADMIN_PASSWORD_HASH = "生成的scrypt哈希"
```

保存后应用会重新启动，并创建 `Admin` 套餐的管理员。随后从“登录”页面使用这组凭证登录，左侧会出现“管理员Dashboard”。

本地首次初始化也可使用 `ADMIN_PASSWORD`，应用会立即将其转换成随机盐 scrypt 哈希，数据库不保存明文。密码至少 12 位。不要同时配置 `ADMIN_PASSWORD` 和 `ADMIN_PASSWORD_HASH`。

### 轮换管理员密码

保持 `ADMIN_USERNAME` 不变，重新生成新的 scrypt 哈希并替换
`ADMIN_PASSWORD_HASH`。应用重启后会更新现有管理员的密码哈希并递增会话版本：

- 旧密码立即失效；
- 旧登录会话在下一次页面交互时退出；
- 数据库和日志仍不保存明文密码。

如果修改了 `ADMIN_USERNAME`，应用不会把已有管理员迁移到新用户名，也不会创建第二个管理员。

初始化是幂等的：数据库中已经存在管理员时不会重复创建，也不会重置密码。如果配置的用户名已被普通账户占用，应用会拒绝自动提权并提示更换用户名。所有者管理员权限不能通过 Dashboard 授予其他用户。

Streamlit Community Cloud 的本地 SQLite 文件不保证永久保存。保留管理员 Secrets，可以在运行环境重建后重新创建管理员。不要把真实密码或哈希提交到 `.env.example`、README、GitHub Issue、日志或聊天记录。

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
7. 检查管理员页能够刷新模型目录，且未知模型不会进入 Auto-Safe 选择结果。
