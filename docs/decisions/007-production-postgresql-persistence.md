# ADR 007：C08 生产持久化使用 PostgreSQL

日期：2026-09-24。状态：已采纳，尚未部署。

## 背景

Streamlit Community Cloud 的本地文件不保证跨重建保留。现有用户 ID、会话版本、报告、用量和加密 Key 相互引用，单独迁移 Key 会造成不可恢复的孤儿数据。生产数据库不可用时继续使用临时 SQLite 会错误暗示数据已经保存。

## 决定

生产通过 `COURSE2CAREER_ENV=production` 与 `DATABASE_URL` 使用标准 PostgreSQL/psycopg 3；URL 必须显式 `sslmode=require`、`verify-ca` 或 `verify-full`，优先 `verify-full` 和托管方 CA。缺少、无效或不可连接时应用停止并显示无敏感内容的错误。开发与离线测试保留 SQLite。数据库边界集中在 `DatabaseBackend`，现有业务仓储 SQL 契约沿用。版本化 schema 由 `schema_migrations` 记录，SQLite 历史升级按版本执行，PostgreSQL 新库在一笔事务中建表。所有生产业务表同时迁移。生产验证徽章只从仓库受控 `verified_models.json` 读取；本地验证脚本输出仍不纳入生产认证。

## 后果

生产必须单独配置、备份和监控数据库与长期加密主密钥。C08 发布之前需要在真实持久后端验证迁移、重连、备份恢复，并完成至少两家大陆 Provider 固定集真实验证。旧 Community Cloud Demo 数据是否迁移由发布负责人审查，不能在部署时默默丢弃或覆盖。
