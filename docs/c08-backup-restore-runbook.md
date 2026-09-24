# C08 PostgreSQL 备份与恢复演练

日期：2026-09-24。本文只针对**独立、空白、使用合成数据的测试库**。生产恢复需单独授权与变更窗口；不得把线上数据库或用户 Key 用于 D1 验证。

## 恢复资产与周期

- 按数据库服务的保留策略定期执行自动备份，并定期验证备份可读取、可恢复；监控失败和备份过期。
- `COURSE2CAREER_KEY_ENCRYPTION_KEY` 是另一项恢复资产。由安全的 Secret 管理渠道独立保存，重部署时保持同一个值；它不能随数据库备份一起公开或提交 Git。
- 恢复 BYOK Key 同时需要数据库备份和**原来的**主密钥。缺少任一项，旧密文不能恢复。错误密钥应安全报错，不能生成替代密钥、清空密文或回退明文。

## 本地配置与安全边界

在本机受保护的环境中设置 `C2C_TEST_DATABASE_URL`、`C2C_TEST_RESTORE_DATABASE_URL` 和 `COURSE2CAREER_KEY_ENCRYPTION_KEY`。两个 URL 必须指向**不同的全新空白 PostgreSQL 测试数据库**，使用标准 PostgreSQL URL 与 TLS；不要把值贴到聊天、命令行参数或 Git。安装与服务器兼容的 `pg_dump`、`pg_restore`。脚本在写入前检查库中无用户表；若已存在表会拒绝。测试库权限需允许建表和恢复。演练产生的本地临时备份在脚本结束时删除。

```powershell
.venv\Scripts\python.exe scripts/verify_remote_persistence.py
```

脚本先在源库迁移 schema，写入合成用户、BYOK 模式、加密假 Key、ProviderProfile、分析及用量，重新连接并核对密文；随后 `pg_dump`、`pg_restore` 到空目标库，再重新连接核对所有业务表与 `schema_migrations` 行数、正确密钥可解密、错误密钥安全失败且密文未变。可用 `--seed-only` 与 `--restore-only` 分两次执行；后者会验证已存在的合成源数据，目标仍必须为空。脚本输出只有状态和行数；错误信息不输出连接信息。

演练记录应保存日期、数据库供应商、客户端和服务器版本、行数、备份和恢复结果、解密结果及操作者；不记录 URL、主机、用户名、密码或 Key。远程演练未实际运行时，状态必须为 PENDING，不能以 CI 容器演练代替。

## CI 容器演练

Draft PR 的 PostgreSQL job 在 `postgres:17` 服务容器中执行合成 SQLite→PostgreSQL 迁移，再在容器中用 `pg_dump` 创建自定义格式备份，恢复到新库。恢复后测试对比全部持久表与 schema 版本，并验证正确／错误主密钥行为。这是 CI 的恢复证据，不能证明独立远程服务或生产恢复已通过。
