# ADR 007：C08 生产持久化使用 PostgreSQL

日期：2026-09-24。状态：已采纳；2026-09-28 已部署独立 PostgreSQL、schema v4。当前契约见[部署说明](../deployment.md)。

## 背景

Streamlit Community Cloud 的本地文件不保证跨重建保留。现有用户 ID、会话版本、报告、用量和加密 Key 相互引用，单独迁移 Key 会造成不可恢复的孤儿数据。生产数据库不可用时继续使用临时 SQLite 会错误暗示数据已经保存。

## 决定

生产通过 `COURSE2CAREER_ENV=production` 与 `DATABASE_URL` 使用 PostgreSQL/psycopg 3；URL 必须显式 `sslmode=verify-full`，连接时使用 certifi CA bundle 验证证书与主机名。最初提案中的 `require`／`verify-ca` 已被现行实现收紧，不可用于生产。缺少、无效或不可连接时应用停止并显示无敏感内容的错误。开发与离线测试保留 SQLite。数据库边界集中在 `DatabaseBackend`，现有业务仓储 SQL 契约沿用。版本化 schema 由 `schema_migrations` 记录；生产当前为 v4，加法迁移不删除已有数据。生产验证徽章只从仓库受控 `verified_models.json` 读取；本地验证脚本输出不能提升生产认证。

## 后果

生产必须单独配置、备份和监控数据库与长期加密主密钥。C08-D1 的远程合成库恢复和两款精确模型验证已完成；生产 schema v4 与核心 smoke 已通过，但合成恢复不等于生产备份演练。旧 Community Cloud Demo SQLite 数据明确不迁移。schema v4 后不得部署只理解 v3 的旧 main；只能使用[已测试的兼容 fallback](../c08-e1-production-release.md)。
