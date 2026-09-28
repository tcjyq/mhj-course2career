# Course2Career 发布后生产同类缺陷修复报告（2026-09-29）

## 范围与状态

基线是 `main` 的 `31cbb0bad399012040a63b8c854ab37fd5bdb279`，修复仅在 `fix/post-release-production-audit` 候选分支。原始问题、复现和证据边界见 [2026-09-28 审计](post-release-production-bug-audit-20260928.md)。本次没有接触生产数据库、Secrets、真实 Provider 或 Cloudflare 生产 Siteverify，也没有合并或部署。生产 E1 的 `RELEASE_READY=yes` 是已发布基线的历史结论；本候选仍需 PR 审查与发布后复测。

按实际安全/隐私影响、可触发性和依赖关系重新排序：`FIX_ORDER=A01 → A03 → A05 → A02 → A06 → A04 → A07 → A08`。A01、A03 是 P1；A02、A04、A05、A06 是 P2；A07、A08 是 P3。A02 的 SDK 默认重试会增加外部请求，但现有 100/120 是**逻辑调用**额度，不足以证明生产重复计费，因此从原 P1 调整为 P2。A07 的示例配置导致本地启动失败，不直接暴露生产凭证，也调整为 P3。A05 的短时暴力尝试风险比 A02 更直接，且共享认证存储路径，先修。顺序表示处理依赖，不表示所有 P2 风险相同。

## 分项修复

| ID / 等级 | 原问题与方案 | 选择理由、文件与回归 | 剩余边界 |
| --- | --- | --- | --- |
| A01 / P1 | 已有 WebSocket 只刷新 `Principal`。现在每次认证态 rerun 都以当前 opaque token 执行服务端 `restore_session`，核对用户与 `session_version`；撤销、过期、失活或不匹配则清理身份与分析状态。 | 复用现有 `auth_sessions`，不新增表；`app.py`、`auth_service.py`、`test_post_release_fixes.py`、`test_auth_restore_state.py`。覆盖撤销、过期、跨用户、版本轮换、F5/新标签恢复及浏览器双标签登出。 | 复核发生在 Streamlit rerun 边界；已经进行中的单次操作不能靠它中途取消。数据库失败保持 fail-closed。 |
| A03 / P1 | 登出后 JD、课程、项目、实习、资料等 widget 可能在同标签页给下一身份看到。现在仅清除分析态，按身份切换递增表单 key epoch，并在清理后的一个运行周期隐藏旧页面体。 | 不使用 `st.session_state.clear()`，保留安装标识和浏览器认证组件；`app.py`、`ui/identity_state.py`、`ui/analysis_page.py`、`ui/candidate_profile_form.py`、`test_post_release_fixes.py`。合成浏览器验证 A→Guest→B 和 B 直接登出后输入不可见。 | 已保存的本人历史仍按数据库授权读取；浏览器缓存、截图或用户已下载文件不由此清除。 |
| A05 / P2 | `guest_session_id` 随新 WebSocket 更换。增加同一规范化用户名的 15 分钟 20 次服务端失败上限，保留单 scope 5 次上限；成功后清除该用户名近期失败记录。 | 使用既有 `login_attempts`，无 IP 唯一键、无新 schema；`auth_service.py`、`user_repository.py`、`test_post_release_fixes.py`。覆盖不同 scope、窗口过期和正常登录。 | 分布式并发检查仍非严格原子；恶意者可让目标账号短时受限，且不构成全局网络级限流。统一登录错误文案仍需保持。 |
| A02 / P2 | 一次逻辑额度遇 500/429/超时可能触发 SDK 自动重试。System OpenAI/DeepSeek generation 显式 `max_retries=0`，目录读取也禁用自动重试；BYOK 保持原语义。DeepSeek 仅在受控 404 缺模型时最多再尝试一个备用模型。 | 最小配置变更，避免新增计费系统；`provider_factory.py`、`llm_client.py`、`llm_providers.py`、`model_catalog.py`、`tests/test_provider_factory.py`、`test_post_release_fixes.py`。MockTransport 验证 500、429、超时各一次请求，404 恰好两次；失败仅一条 `api_usage` 预留且不自动退回。 | 100/120 仍是逻辑调用上限，不等于 Provider HTTP/货币绝对上限；404 fallback 可有第二次请求，连接中断后的服务端实际处理不可从客户端证明。 |
| A06 / P2 | Key 写成功而 Profile 写失败会留下半配置。先在 service 层验证并生成加密对象，再以同一 repository 连接事务写入两者。 | 不取回旧明文、不改变加密；`api_key_service.py`、`provider_profile.py`、`product_repository.py`、`ui/developer_page.py`、`test_post_release_fixes.py`。SQLite 注入第二次写失败，旧 Key/Profile 均保持；PostgreSQL 标记测试复用同一断言。 | 只覆盖同一 Provider 的配置保存；Provider 连接探测依然是独立操作。 |
| A04 / P2 | CSV 的不可信技能/课程文本可能被表格软件解释为公式。导出时对危险前缀补单引号，保留 `csv.writer` 与 UTF-8 BOM。 | `report_exporter.py`、`test_post_release_fixes.py`。覆盖 `= + - @`、正常中文、数值、引号、逗号、换行。 | OWASP 指出 CSV 注入不存在跨所有表格工具/重新保存流程的通用防护；本测试未实测 Excel/Calc 的保存后再打开，不应宣称所有客户端绝对安全。 |
| A07 / P3 | `.env.example` 的管理员示例像有效配置却不符合密码规则，模型示例过时。管理员三项默认空，模型示例指向受控 `deepseek-flash`。 | `.env.example`、`tests/test_post_release_fixes.py`；测试模板值和 VERIFIED 文件。 | 启用管理员仍需操作员单独设置强凭证；示例不是生产 Secrets。 |
| A08 / P3 | 当前部署文档/ADR 把已上线 PostgreSQL 当成待部署，TLS 口径过松。修正文档顶部和当前部署段落，明确 schema v4、`verify-full`、certifi、独立生产库、旧 SQLite 不迁移及 v4 兼容 fallback。 | `README.md`、`docs/deployment.md`、`docs/architecture.md`、`docs/requirements.md`、`docs/user-guide.md`、`docs/ui-design.md`、相关 ADR、`docs/development-log.md`、`docs/evaluation.md`。历史日志保留当时事实，新增当前状态链接。 | 当前生产的 Admin、已认证 Developer Mode、BYOK 人工回归仍是 `MANUAL_PENDING`；文档修复不等于这些路径已经生产复测。 |

## 验证与证据边界

- 本地 Python 3.12 虚拟环境完整 pytest 为 **302 passed、6 skipped**；Ruff lint、Ruff format（105 个文件）、`git diff --check` 均通过。原 `main` 审计基线为 291 通过、5 个本机 PostgreSQL 标记用例跳过；新增的 PostgreSQL A01/A05/A06 测试是第 6 个跳过项，须由 PR 的 PostgreSQL 3.12/3.14 CI 实跑。当前 Windows 环境没有可用的 Docker/Podman/本机 PostgreSQL 测试实例，不连接生产或远程测试库补数。
- 本地真实浏览器仅使用合成账号、合成 JD 和 SQLite：登录、F5、新标签、双标签登出、A→Guest→B 的未保存输入隔离、本地规则分析、CSV 实际下载均已验证；合成 B 登录后可打开并启用 Developer Mode。该本地服务没有加密主密钥，故页面按既有安全逻辑阻止保存 BYOK Key，未进行真实 BYOK/Provider 调用。浏览器仍见两个既有 `_stcore` 子路由 404，与原审计相同。此项不是生产浏览器 smoke。
- System AI 页面在无平台 Key 的本地合成环境不能展示可调用选项；现有 AppTest 使用合成配置检查页面与配额路径。不得把这项记为真实浏览器 System AI 通过。没有任何真实 Provider API 请求。
- 首轮 PR CI 的 PostgreSQL 3.12 集成步骤通过，但随后备份恢复资产断言失败：新增的 PG 测试清空/增加了与既有备份恢复用例共用的合成库数据。这是测试隔离缺陷，并非生产数据变化。已改为唯一合成账号并在 `finally` 中只清理本用例创建的行，不再 `TRUNCATE` 共用库。[修正后 CI run 36455373024](https://github.com/tcjyq/mhj-course2career/actions/runs/36455373024) 的 quality 3.11/3.12/3.14 与 PostgreSQL 集成加备份恢复 3.12/3.14 均成功（5/5）。
- 对 15 类模式重新检索与追踪：1 登录/session、2 `dict_row`、3 SQLite/PostgreSQL、4 TLS/网络、5 Provider retry/fallback、6 Streamlit rerun、7 认证与限流、8 Turnstile、9 System quota、10 migration/rollback、11 Secret/log、12 原子性、13 浏览器信任/XSS、14 文件/导出/输入、15 配置/文档漂移。未发现本次修复新增的 P0/P1/P2/P3 确认缺陷；此为代码审计结论，不代替生产监控或渗透测试。原有 localStorage token 不能 HttpOnly、Turnstile 不能阻止人工滥用、100/120 非货币上限、旧路径人工回归待做等边界仍在。

## 关键参考

- [Streamlit Session State 与 WebSocket 生命周期](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.session_state)、[widget 清理规则](https://docs.streamlit.io/develop/concepts/architecture/widget-behavior)、[页面切换 API](https://docs.streamlit.io/develop/api-reference/navigation/st.switch_page)：支持 A01/A03 的 rerun 和 widget 边界判断。
- [OpenAI Python SDK 默认重试与 `max_retries`](https://github.com/openai/openai-python#retries)：支持 A02 的显式禁重试。
- [OWASP CSV Injection](https://community.owasp.org/attacks/CSV_Injection)、[OWASP ASVS 输出编码](https://cornucopia.owasp.org/taxonomy/asvs-5.0/01-encoding-and-sanitization/02-injection-prevention)：支持 A04 的风险和客户端兼容局限。
- [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html)：支持 A05 的短时节流和统一错误策略。
- [psycopg 3 事务文档](https://www.psycopg.org/psycopg3/docs/basic/transactions.html)、[Python sqlite3 事务控制](https://docs.python.org/3/library/sqlite3.html#transaction-control)：支持 A06 的单连接事务边界。

## 合并判断

本报告记录的是候选分支修复和可复查证据。只有最终检查与 PR 五项 CI 全绿、差异无敏感内容、审阅人接受上述残余边界后，才能把 `SAFE_TO_MERGE` 标为 yes；本任务不合并 PR。生产上线后仍需另做 A01/A03/BYOK 的非破坏性 smoke，不把本地合成测试说成线上通过。
