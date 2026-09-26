# C08-D2 Release Candidate Report

日期：2026-09-26（北京时间）。范围：Draft [PR #2](https://github.com/tcjyq/mhj-course2career/pull/2) 的 `feature/c08-multi-provider`。这是作品集/公共 Demo 的 Pre-Release Blocker Closure，不是上线批准。本轮没有真实 Provider API 请求，没有合并、部署或修改生产 Secrets/数据库。

## 结论与状态

| 门槛 | 状态 | 证据边界 |
|---|---|---|
| `ARCHITECTURE_READY` | yes | D0 受控 Provider 端点与生产持久化边界 |
| `POSTGRES_CI_READY` / `REMOTE_POSTGRES_READY` / `BACKUP_RESTORE_READY` | yes | D1 CI 与独立远程**合成**库的备份恢复；不代表生产库已创建或备份 |
| `PERSISTENCE_READY` | yes | D1 与生产 fail-closed 回归；C08 新生产库尚待人工创建 |
| `PROVIDER_VALIDATED` | yes | 仅 Bailian `cn-beijing` / `qwen3.8-flash`、DeepSeek `global` / `deepseek-flash` 的 D1 精确认证；D2 未重测 |
| `SYNTHETIC_E2E_READY` | yes | 本地 SQLite 服务链、fake Provider、AppTest、浏览器规则流及 D1 PostgreSQL CI 分层证据；不声称一次 UI→真实模型→生产库全链路 |
| `BROWSER_READY` | yes | 隔离本地 Streamlit 桌面与 390px 实测；直接深链接有已知 `_stcore` 探测 404，见下文 |
| `SECURITY_REVIEW_READY` | yes | 独立只读复核发现的生产 TLS、跨账户状态和无费率 Provider 渲染问题已修复；历史凭证模式扫描见下文 |
| `RELEASE_CANDIDATE_READY` | yes | D2 代码提交 `5761c0d7` 的五个 PR CI 作业均通过；候选可供人工生产配置审查 |
| `PRODUCTION_SECRETS_READY` / `RELEASE_READY` | no / no | 独立生产 PostgreSQL、主密钥和 Streamlit Secrets 尚未人工配置/确认 |

## 已关闭的阻断项

1. **旧 Demo 数据处置。** 当前 Community Cloud SQLite 明确定义为 **disposable demo state**。C08 从全新、独立 production PostgreSQL 开始；旧 Demo 账号、历史和临时 Key 不迁移。生产入口不读取旧 SQLite，不运行自动迁移，也不做 SQLite → PostgreSQL 在线切换。仓库里的迁移脚本仍需操作员显式给出快照和 `--acknowledge-source-data`，本轮未用于线上数据。
2. **生产数据库边界。** `COURSE2CAREER_ENV=production` 要求 `DATABASE_URL` 指向独立 production PostgreSQL，代码只接受 `sslmode=verify-full`；缺失、不合格或不可达时 fail closed，不回退 SQLite。`C08_TEST_DATABASE_URL`、`C08_TEST_RESTORE_DATABASE_URL` 和 D1 测试库不用于生产。`COURSE2CAREER_KEY_ENCRYPTION_KEY` 不自动生成，重部署须保持原值。根级 Streamlit Secrets 与 OS 环境走同一配置读取路径（`test_root_streamlit_secrets_and_os_environment_share_config`）；`.env`、`.streamlit/secrets.toml` 被 Git 忽略。System DeepSeek 实际使用的 Secret 名为 `DEEPSEEK_API_KEY`。本轮只核对变量名和代码路径，未读取生产 Secret 值。
3. **分析前提示。** “提取岗位技能”按钮前，本地规则说明 JD 不发给第三方模型；AI 模式说明 JD 将发给所选 Provider；BYOK 提醒可能产生持有人账单。费率不存在或未配置时显示“费用未知/未配置”，不把 unknown 当 free。独立复核发现 `(None, None)` 费率会导致页面 TypeError，已修复并用 Anthropic BYOK AppTest 覆盖。
4. **账户边界。** Provider 的临时连接状态按当前 user ID、端点和模型匹配；保存或删除配置会清理旧状态。同浏览器切换账户不会把上一账户的连接测试提示当作新账户结果。Key 密文仍按用户与 Provider 的 AES-GCM 关联数据绑定，服务层查询和 BYOK 授权保持用户隔离。

## 验证记录

- **离线合成路径：** 注册/登录、启用开发者模式、保存加密合成 Key 和 DeepSeek Profile、fake Provider 分析、用量与报告持久化、重新连接、关闭/重开 BYOK、跨用户 Key/Profile/历史拒绝均通过。fake Provider 使用本地规则构造响应，不代表 DeepSeek 真实调用。`test_production_without_database_fails_closed` 和 `test_production_entry_requires_verified_postgres_hostname` 分别覆盖缺库及 TLS 策略；数据库不可达由既有 CI 与安全错误路径覆盖。本地 SQLite 不等于 PostgreSQL 端到端；D1 PostgreSQL CI 单独承接真实数据库集成。
- **桌面真实浏览器：** 本地隔离 Streamlit 1280px，使用合成账户完成注册、登录、会员页、开发者模式、Provider Hub 保存假 Key、分析页本地规则、合成 Excel 上传、合成 JD 提取、报告生成与历史保存（41.2 分）、退出/重新登录及历史恢复。AI 模式仅检查提交前提示，没有按“测试连接”或付费提取按钮；没有真实 Provider 请求。桌面页面 `scrollWidth=innerWidth=1280`，关键操作可用。
- **390px 真实浏览器：** 登录、[Provider Hub](../screenshots/c08-d2-provider-mobile.png) 和[分析页本地规则提示](../screenshots/c08-d2-analysis-notice-mobile.png)可见，无整体横向溢出；实测 `documentElement.scrollWidth=body.scrollWidth=innerWidth=390`。另存[移动登录截图](../screenshots/c08-d2-login-mobile.png)。Provider 页可见已配置的假 Key 后四位、精确模型状态与费用未知提示；无文案遮挡。直接输入 Streamlit 子页面 URL 时，浏览器控制台有 `_stcore/health`、`_stcore/host-config` 404 探测，且新导航会话回到访客；这是已知深链接探测边界，不能记为“零 console error”。正常页面交互未见业务相关 JS 错误。
- **独立只读审查：** 审阅 auth/access、Key 加密与用户隔离、生产 PostgreSQL、BYOK 额度、官方端点与重定向限制、受控精确模型认证。初审发现生产 TLS 模式过宽，复核发现无费率 Provider 渲染错误；均已在本提交修复。未发现需要重新设计产品的阻断项。
- **Git tracked history 凭证模式扫描：** `real_secret_findings = 0`；测试/示例占位模式 12 个，代码变量引用模式 28 个（历史及本次暂存差异中去重后的匹配项）。扫描检查所有可达提交及本次暂存的新增文本行，覆盖常见 API Key 前缀与关键变量赋值；不输出匹配值。该模式扫描不能证明不存在所有未知格式的凭证，也未读取生产 Secrets。
- **本地及 PR CI：** Python 3.12 与 3.14 各收集 260 项、258 passed / 2 skipped（两个 skip 为需独立 PostgreSQL 服务的测试，交由 PR 的 PostgreSQL jobs 承接）；3.14 `pip check` 无依赖冲突；`ruff check .`、`ruff format --check .`、`git diff --check` 和暂存差异检查通过。D2 代码提交 `5761c0d7` 的 [CI Run 36237182862](https://github.com/tcjyq/mhj-course2career/actions/runs/36237182862) 中 Python 3.11/3.12/3.14 quality 与 PostgreSQL 3.12/3.14 五个作业全部成功。

## Remaining human actions

1. 创建独立 production PostgreSQL，使用可验证主机名的 TLS 连接，不复用 D1 测试库。
2. 生成独立 production encryption master key，安全保存且重部署保持同一值。
3. 配置 Streamlit production 根级 Secrets：`COURSE2CAREER_ENV`、`DATABASE_URL`、`COURSE2CAREER_KEY_ENCRYPTION_KEY`；仅在启用 System DeepSeek 时另配 `DEEPSEEK_API_KEY`。
4. 人工确认 Secrets 保存成功及目标应用/分支配置无误，不在审查记录中暴露值。
5. 单独给出最终 merge authorization；在此之前 PR #2 保持 Draft、`RELEASE_READY=no`，不合并、不部署。
