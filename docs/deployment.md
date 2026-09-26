# 部署说明

## 当前定位

当前版本适合本地运行、作品集演示和受控测试。开放系统 AI 能力前，应先完成限流、真实 Token/费用统计、权限会话失效和全局预算熔断。

同一次部署同时修改入口文件和业务模块时，Streamlit 可能短暂保留旧模块缓存。入口层的依赖注入应兼容该热重载窗口；若页面出现构造函数参数不一致错误，应先等待部署完成并重启应用，而不是修改 Secrets。

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
- `COURSE2CAREER_ENV` / `DATABASE_URL`（正式 BYOK 生产环境必需；前者设为 `production`）
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

### 作品集 Demo 的数据边界

当前 Streamlit Community Cloud 的 SQLite 明确定义为 **disposable demo state**，不保证持久性。未设置 `COURSE2CAREER_DATABASE_PATH` 时，旧部署使用 `instance/course2career.db`；这不是对线上数据量或备份状态的核验。C08 发布使用全新、独立的 production PostgreSQL：旧 Demo 账号、历史和临时 Key 不迁移，用户需在新库重新注册及配置。不会执行生产 SQLite 自动迁移，也不进行 SQLite → PostgreSQL 在线切换。

初始化采用幂等建表及管理员初始化逻辑；保留管理员 Secrets 不等于备份全部账户、报告或额度记录。C01—C07 没有 SQLite 表结构迁移，只有报告 JSON 新增可选 `sources`、`task`、`completion_criteria` 字段：新版本可读取旧快照，基线版本的严格模型会拒绝含新字段的快照。代码回退与数据恢复必须分别处理，不能直接覆盖或删除生产数据库。

C08-B1 的 SQLite schema 升级只适用于本地或保留旧数据的显式 SQLite 实例；C08 生产使用全新 PostgreSQL，启动时不会读取或迁移线上 SQLite。独立的 `scripts/migrate_sqlite_to_postgres.py` 需要操作员显式给出已审查快照和 `--acknowledge-source-data`，不属于生产启动路径。本轮不会运行该工具处理线上数据。

C08-D0 分支已加入 PostgreSQL 持久路径与合成数据迁移；D1 的 Draft PR 只用于 CI。公开演示目前仍使用旧 SQLite；即使 feature 分支通过 CI，也不能据此认为线上数据已迁移。[持久化设计与数据分类](c08-production-persistence.md)。

### 生产运行时与发布门槛

2026-09-22 用户确认当前 Community Cloud Python 为 3.14，Sharing 为 Public and searchable。仓库、README 链接和入口文件与 `tcjyq/mhj-course2career` / `main` / `app.py` 高度一致，但平台内部绑定无法从当前授权渠道直接读取；不能把仓库结构或公开 HTTP 200 当作绑定证明。

发布流程为 release branch → PR CI → 经授权合入 main → Streamlit smoke test → Showcase。CI 保留 Python 3.11／3.12，并覆盖生产使用的 3.14；本地 Windows 测试不替代远端 Linux CI 或生产验收。`requires-python >=3.11` 与 Ruff 的 `py311` 目标保留最低支持版本，不限制使用 3.14。依赖安装使用原有固定版本，不通过取消 pin 规避兼容问题。

Community Cloud 可随绑定分支更新而自动更新应用，因此合入 main 属于潜在生产变更，不能在 PR CI 通过前直接推送 main。当前发布候选及各环境实际验证结果见 [发布复核记录](optimization-review.md)。

## 启动

```powershell
python -m pip install -r requirements.txt
streamlit run app.py
```

## 招聘 Showcase（Cloudflare）

`showcase/` 是静态 Cloudflare Worker，不部署 Python 应用、不设置数据库或 API Key。首次发布前，确认 Cloudflare 账户拥有 `tcjyq.cc` 区域并允许 Worker Custom Domain；随后执行：

```powershell
npx wrangler deploy --config showcase/wrangler.jsonc
```

该配置以 `course2career.tcjyq.cc` 作为 Custom Domain route，并从 `showcase/public/` 提供静态文件。部署后以无痕窗口访问 `https://course2career.tcjyq.cc`：应直接显示 Showcase，而不是 302 跳转到 Streamlit。Cloudflare 静态资产与 Custom Domain route 的配置语义见 [Workers Static Assets](https://developers.cloudflare.com/workers/static-assets/) 与 [Custom Domains](https://developers.cloudflare.com/workers/configuration/routing/custom-domains/)。

Streamlit Community Cloud 中应将应用 Sharing 设为 **Public**。不要把平台 API Key 写入 Cloudflare、仓库或公开 Secrets；未配置平台 AI Key 时，应用只显示默认的本地规则模式。Community Cloud 的休眠由平台管理，不添加 ping、定时任务或其他保活机制。

## 发布前检查

1. 测试、Ruff 和格式检查全部通过。
2. 仓库中不存在 `.env`、数据库、日志、缓存或真实凭证。
3. 使用 HTTPS，并在反向代理层设置请求速率、并发和上传大小限制。
4. 备份数据库与 API Key 加密主密钥，但两者分开保存。
5. 不把用户课程、完整 JD、密码或 API Key 写入日志。
6. 公开页面提供隐私说明和第三方模型数据传输提示。
7. 检查管理员页能够刷新模型目录，且未知模型不会进入 Auto-Safe 选择结果。

## C08-D0/D1 生产 PostgreSQL 准备

正式启用 BYOK 前，在 Community Cloud 根级 Secrets 中配置 `COURSE2CAREER_ENV="production"`、`DATABASE_URL="postgresql://USER:PASSWORD@HOST/DB?sslmode=verify-full"` 与长期保存的 `COURSE2CAREER_KEY_ENCRYPTION_KEY`。示例仅为占位值；实际凭证不能进入仓库、截图、日志或聊天。此 URL 必须指向独立 production PostgreSQL，不能使用 `C2C_TEST_DATABASE_URL`、`C2C_TEST_RESTORE_DATABASE_URL` 或 D1 测试库。生产入口只接受 `sslmode=verify-full`，须核验托管方 CA 及服务端主机名；缺 URL、TLS 配置不合格或连接失败时应用停止，不回退 SQLite。`.env` 和 `.streamlit/secrets.toml` 已忽略。

生产数据库应启用托管备份并限定权限。主密钥与数据库备份分开保存，重部署必须保持同一值；程序不会自动生成替代主密钥。D1 的[备份恢复操作说明](c08-backup-restore-runbook.md)及远程演练仅针对独立合成测试库，不代表生产备份已配置。D1 PostgreSQL CI、远程合成库、备份恢复及两款精确 Provider 模型认证已通过；D2 候选审查与生产 Secrets 配置已由用户人工确认完成。PR #2 已合并；生产运行时验收仍未通过，`RELEASE_READY=no`。

生产部署所需的核心 Secret 名称仅为 `COURSE2CAREER_ENV`、`DATABASE_URL`、`COURSE2CAREER_KEY_ENCRYPTION_KEY`；如启用当前 System DeepSeek，还需代码读取的 `DEEPSEEK_API_KEY`。将它们放在 Streamlit Community Cloud **App Settings → Secrets** 的根级配置，或等价的 OS 环境变量。应用通过同一配置读取路径获取根级 Secrets；不要在文档、仓库或日志中记录实际值。用户已确认独立 production PostgreSQL、独立长期主密钥以及四项 Streamlit 根级 Secrets 均已创建或保存；本次只核对名称，不读取值。生产仓储初始化失败时，页面仅显示统一安全提示；Cloud logs 仅记录 `database_startup_failure`、安全异常类型和固定故障类别，不输出连接 URL、凭证或原始异常。生产连接仍要求 `sslmode=verify-full`，失败后停止且不回退 SQLite。
