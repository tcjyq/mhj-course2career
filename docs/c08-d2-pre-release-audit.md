# C08-D2 Pre-Release Audit

> 这是 2026-09-26 的审计基线，以下“阻断项”记录当时的发现，不代表最新开放状态。用户随后决定旧线上 SQLite 为 disposable demo state，C08 从全新独立生产 PostgreSQL 开始；本轮关闭结果及仍需人工完成的生产步骤以 [C08-D2 Release Candidate Report](c08-d2-release-candidate.md) 为准。

审计日期：2026-09-26（北京时间）。范围为 `feature/c08-multi-provider` 的 `6ec815f2f07ea89fb82796d3f3bbbcadd8e88325`、[PR #2](https://github.com/tcjyq/mhj-course2career/pull/2)、仓库代码和现有文档。审计只读取远端 PR/CI；没有重新调用真实 Provider API，没有连接或修改生产数据库、Secrets，也没有合并或部署。

## 结论

**Pre-Release Audit 已执行；C08-D2 Release Gate 暂缓，`RELEASE_READY=no`。** D1 的架构、持久化和两款精确模型认证门槛保持 `yes`，但它们不是生产切换、隐私/费用验收或回退演练的替代证据。PR #2 保持 Draft。

## 已核实的证据

| 项目 | 结果与边界 |
|---|---|
| Git / PR | 工作分支 HEAD 与 PR head 均为上述 SHA；base `main` 为 `3c9378683640bfbeb1ddcaec1a909a8ca0286c82`。PR Open、Draft、无 review；差异为 85 个文件、8052 行新增、269 行删除。仓库原有两份未跟踪文档，审计未改动。 |
| 最新 CI | [Run 36231376678](https://github.com/tcjyq/mhj-course2career/actions/runs/36231376678) 对该 SHA 的 3.11/3.12/3.14 quality 和 3.12/3.14 PostgreSQL job 全部成功。三个 quality job 各为 250 passed、2 skipped；PostgreSQL job 分别覆盖合成迁移、`pg_dump`/`pg_restore` 和恢复后解密。quality 中的两个 skip 由独立 PostgreSQL job 承接。 |
| 本机离线核查 | 项目 `.venv`（Python 3.12.14）的非 PostgreSQL pytest 完成且退出码 0；Ruff lint、format、`git diff --check` 均通过。初次误用系统 Python 的收集错误不计为项目测试结果。没有运行收费验证或远程数据库脚本。 |
| D1 模型认证 | [受控文件](../src/course2career/verified_models.json)只含 Bailian `cn-beijing` / `qwen3.8-flash` 和 DeepSeek `global` / `deepseek-flash`，各 4/4、usage 可用、返回模型一致；依据为此前的[本机真实验证记录](c08-provider-validation.md)，本次没有重测，不能推及其他模型。 |
| D1 独立远程库 | `REMOTE_POSTGRES_READY=yes` 与 `BACKUP_RESTORE_READY=yes` 依据此前[开发日志](development-log.md)和[演练说明](c08-backup-restore-runbook.md)；本次未重连。独立合成库恢复成功不证明生产数据已备份、迁移或恢复。 |

## 发布阻断项

1. **生产数据切换与回退方案未定。** [持久化设计](c08-production-persistence.md)明确指出线上 SQLite 数据是否保留尚未决定。需先确定数据保留/迁移范围、取得一致性快照的方法、逐表行数与密文核验、切换窗口，以及上线后有新账户/报告/用量写入时的回退办法。不能把合成库 `pg_restore` 成功当成生产恢复成功，也不能以回滚代码覆盖生产数据库。实际快照、迁移和恢复需另获生产操作授权。
2. **生产配置和运行保障缺少直接证据。** 尚未从 Streamlit Community Cloud 设置直接核实应用绑定、目标 Python/分支、`COURSE2CAREER_ENV`、持久 `DATABASE_URL`、长期加密主密钥、数据库备份保留期、最小权限、可用性/备份告警及值班处置。只记录配置是否合格，不采集 Secret 值。[数据库边界](../src/course2career/database_backend.py)目前允许 `sslmode=require`、`verify-ca` 和 `verify-full`；前两者不足以同时验证服务器主机名。发布配置应采用 `verify-full` 与可信 CA，并在合成环境验证；若要代码强制，该改动须另行测试。
3. **隐私与费用的用户触点尚未验收。** [用户指南](user-guide.md)说明 JD 会发送第三方，[Provider 页](../src/course2career/ui/developer_page.py)说明 BYOK 费用，但[分析页](../src/course2career/ui/analysis_page.py)的实际付费提交前没有紧邻操作的第三方数据传输/费用提示。需确认数据保留与删除说明、对不同地区 Provider 的告知、未知价格如何显示，以及平台系统 AI 的预算上限、异常用量监控与停用路径。现有 `cost_status=unknown` 是诚实记录，不能视作成本控制已完成。
4. **D2 端到端证据不足。** 现有 D1 固定 JD 认证和 fake/AppTest/CI 分别验证不同契约；仍缺隔离沙盒中以合成账户跑完整登录、BYOK 开关、Key 保存/清除、精确模型选择、分析、用量回写、跨用户拒绝、数据库故障、重启恢复的记录，以及桌面/390px 真实浏览器和可访问性回归。涉及真实模型的沙盒步骤本轮不执行，也不重复 Provider API 验证；是否复用 D1 证据须逐项界定。
5. **审阅和说明尚未收口。** PR #2 无 review，描述仍写远程 PostgreSQL 与两款模型验证待完成，且仅引用 2026-09-24 旧 CI。`c08-multi-provider-design.md`、`c08-model-discovery.md` 仍写“无 VERIFIED”；`access-control.md` 仍写 Free/Pro 不能 BYOK；`architecture.md` 仍写独立 CI/恢复待完成。应在发布评审前校正文档、PR 描述及示例/截图状态，并完成针对 85 文件跨层改动的独立代码、安全及凭证历史审阅。当前仅核对 Git 跟踪文件名未含 `.env`、`secrets.toml`、数据库和本机验证输出；未做完整历史密钥扫描。

## D2 后续顺序

先在 feature 分支处理本报告的代码/文案和文档项，完成无需生产权限的合成沙盒、真实浏览器与安全复核；再形成可审阅的生产数据处置、监控和回退方案，并对 PR 做独立 review。最后才核验平台实际配置与生产迁移前条件；这些步骤不自动授权合并、部署、修改 Secrets 或生产数据库。每项须附日期、环境、候选 SHA、结果与可脱敏证据。任何代码或配置变化后重新核对 CI 与受影响门槛；`RELEASE_READY` 在所有阻断项关闭并完成 D2 Release Gate 审查前维持 `no`。
