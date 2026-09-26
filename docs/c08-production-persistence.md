# C08-D0/D1 生产持久化与发布门槛

日期：2026-09-24。基线：C08-C `c669b74fc09293b137a1a35a9e0d777d4cbda9b7`；D0 `607f93a0815f825be0c80cc62ac45d0644e072e5`。D1 仅验证 feature 分支；没有合入或部署。

## SQLite 完整清单

| 表或状态 | 分类 | 理由 |
|---|---|
| `users` | DURABLE | ID、角色、套餐、密码哈希、会话版本及停用状态 |
| `login_attempts` | DURABLE | 登录节流跨进程生效；可按保留期清理 |
| `api_usage` | DURABLE | 用量、额度、费用与预留状态 |
| `analysis_records` | DURABLE | 用户保存的完整分析快照 |
| `user_api_keys` | DURABLE | AES-256-GCM 密文、nonce、归属与最后四位 |
| `user_provider_profiles` | DURABLE | Provider、端点、模型和业务空间偏好 |
| `user_byok_settings` | DURABLE | 自助开发者模式开关与停用后的授权 |
| `schema_migrations` | DURABLE | schema 版本与升级审计 |
| `ModelCatalogService._cache`、DeepSeek 模型缓存 | CACHE | 仅无密钥目录数据；丢失后重新查询或显示静态候选，不可产生 VERIFIED |
| Streamlit `session_state`、临时连接测试 | EPHEMERAL | 仅当前会话；每次敏感操作仍查持久状态 |
| `outputs/c08-provider-validation/records.json` | EPHEMERAL（本地证据） | 忽略版本控制，不可作为生产认证 |
| `src/course2career/verified_models.json` | 受控版本证据 | 生产 VERIFIED 的唯一项目认证来源；现只包含 Bailian `cn-beijing` / `qwen3.8-flash` 和 DeepSeek `global` / `deepseek-flash` 两个精确记录 |

## 生产配置与安全

本地默认 `COURSE2CAREER_DATABASE_PATH=instance/course2career.db`。生产必须设置 `COURSE2CAREER_ENV=production` 和指向独立 production PostgreSQL 的 `DATABASE_URL`，其中 `sslmode=verify-full`；不接受 `sslmode=require` 或 `verify-ca`。Community Cloud 的根级 Secrets 可作为环境变量读取；`.env` 与 `.streamlit/secrets.toml` 已被 Git 忽略。生产没有 URL、TLS 校验不合格或数据库不可达时应用停止并显示安全错误，不会切回 SQLite。生产不能使用 `C2C_TEST_DATABASE_URL`、`C2C_TEST_RESTORE_DATABASE_URL`、D1 测试库或本地无 TLS 测试开关。

`COURSE2CAREER_KEY_ENCRYPTION_KEY` 是 32 字节 Base64 AES-GCM 主密钥的**长期 Secret**，必须在重启、重部署和数据库恢复后保持一致，与数据库备份分开存放。更换它会使旧密文不能解密；程序不会自行生成替代主密钥。未配置时 BYOK Key 功能不可用。数据库只存密文、nonce 和后四位；不记录明文、连接 URL、错误原文或完整模型请求。生产应采用最小权限账户、托管数据库备份及定期恢复演练，并对数据库可用性和备份失败告警。

## Migration contract

`schema_migrations` 的 1 是用户/登录基础 schema，2 是 C08 完整产品 schema。旧 C01—C07、C08-A/B/C SQLite 无版本表时依序升级；执行失败不写成功版本，已存在的表继续由 `CREATE IF NOT EXISTS` 和旧约束兼容逻辑处理。新 PostgreSQL 在同一事务中创建全部表和版本记录；未来变更必须新增顺序版本，不能改写已有版本。数据库版本高于代码或出现未知 PostgreSQL 版本时拒绝启动。SQLite 旧表约束重建仍用事务，保留密文与关联数据。

`python scripts/migrate_sqlite_to_postgres.py <已审查的备份路径> --acknowledge-source-data` 是操作员显式运行的离线工具，可从只读 SQLite 快照复制全部 7 张 DURABLE 业务表到**空** PostgreSQL；它不在应用启动时执行。C08 的生产决策已经明确：当前 Streamlit Community Cloud SQLite 为 **disposable demo state**，旧 Demo 账号、历史和临时 Key 不迁移；正式版本从全新 production PostgreSQL 开始，不做生产 SQLite 自动迁移或在线切换。该工具只保留供独立合成测试和将来另行授权的离线数据任务使用。

## 验证与发布状态

本地 SQLite 全套测试及 PostgreSQL 独立 CI job 使用合成账户、假 Key、报告和用量。CI 使用仅限 localhost 的无 TLS 测试连接；生产入口强制 `verify-full`。PostgreSQL job 覆盖建库、幂等重连、注册登录、BYOK 关闭/重开、密文解密、Profile、报告、额度/用量、跨用户隔离及合成迁移。D1 还增加容器内备份、空库恢复、行数与主密钥验证。2026-09-26 Draft PR 的 D1 提交已通过 PostgreSQL 3.12/3.14 CI、备份恢复及恢复后解密。独立远程 PostgreSQL 合成演练的完成状态来自此前[开发日志](development-log.md)中的远程 restore-only 行数、正确密钥解密和错误密钥拒绝记录；D2 不重新连接远程数据库，远程 PASS 不等于生产恢复。D2 候选提交须单独复核 CI；结果见[候选报告](c08-d2-release-candidate.md)。

状态条件：`ARCHITECTURE_READY` 要求设计与受控端点；`PERSISTENCE_READY` 要求 PostgreSQL CI、独立远程测试、备份恢复、恢复后解密及生产 fail-closed 全部通过；`PROVIDER_VALIDATED` 要求至少 DeepSeek 与百炼各有一个精确模型通过 B2 固定合成集。2026-09-26 已精确认证 Bailian `qwen3.8-flash` 和 DeepSeek `deepseek-flash`。D2 Pre-Release Blocker Closure 的结果以[候选报告](c08-d2-release-candidate.md)为准；用户已确认生产库、长期主密钥及 Streamlit 根级 Secrets 配置完成，值未读取，生产运行时未验收。`RELEASE_READY=no`；Draft PR 未获合并与部署授权。

| D1 状态 | 当前值 | 依据与边界 |
|---|---|---|
| `ARCHITECTURE_READY` | yes | D0 架构与受控端点保持不变 |
| `POSTGRES_CI_READY` | yes | Draft PR 的 PostgreSQL 3.12/3.14 合成集成、备份恢复与解密 job 已通过；认证提交自身 CI 单独复核 |
| `REMOTE_POSTGRES_READY` | yes | 先前独立远程合成演练记录；本轮不连接或修改远端 |
| `BACKUP_RESTORE_READY` | yes | CI 容器演练及先前独立远程恢复；恢复后正确密钥解密、错误密钥安全失败均有记录 |
| `PERSISTENCE_READY` | yes | 上述证据和 fail-closed 离线回归满足 D1 门槛；不代表生产迁移已执行 |
| `PROVIDER_VALIDATED` | yes | 两条精确模型认证均满足 4/4 固定集、usage、返回模型及零错误 |
| `RELEASE_READY` | no | D2 候选审查已执行，生产资源与 Secrets 已由用户人工确认；尚未合并、部署或完成生产运行时验收 |
