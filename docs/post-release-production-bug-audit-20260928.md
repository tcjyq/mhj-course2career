# Course2Career 生产同类缺陷审计（2026-09-28）

## 范围与证据边界

- 基线：本地和 GitHub `main` 均为 `31cbb0bad399012040a63b8c854ab37fd5bdb279`；GitHub CI run `36430628817` 为 success。本报告未访问生产数据库、Secrets、Cloudflare 配置或真实 Provider。
- 审查：`app.py`、35 个业务/UI/数据库相关源文件（含题定调用链）、6 个测试模块的相关用例，以及 16 个 README、部署、ADR、配置和 CI 文件的相关段落。全仓以高风险模式检索并追踪调用路径；“检索过”不等于“逐行审查过”。
- 本机验证：296 个 pytest 用例中 291 通过、5 个 PostgreSQL 标记用例因未提供**本机**合成库而跳过；Ruff lint、Ruff format 检查通过。基线的 GitHub PostgreSQL 3.12/3.14 job 成功，但本轮新发现没有在 PostgreSQL 容器或生产浏览器中重放。
- 隔离复现使用合成账号、合成 JD、`httpx.MockTransport`、假 Provider、无凭证测试值和 Streamlit AppTest；不包含真实外部请求。当前仓库没有 `C08_TEST_DATABASE_URL` / `DATABASE_URL` 环境变量。历史“测试账号随机密码曾出现在任务工具日志”的事件继续按发布记录记为 **contained**；本轮未读取该密码，仓库扫描不能代替任务日志或生产日志审计。
- 严重度：P0=0，P1=3，P2=4，P3=1。状态：CONFIRMED=6，HIGH_CONFIDENCE=2，NEEDS_REPRO=0。HIGH_CONFIDENCE 的生产浏览器或故障注入验证仍是建议的后续工作，不能表述为生产已复现。

## 发现

### C2C-A01 — 已撤销或过期的登录会话仍能在已有 WebSocket 中继续使用

- ID = C2C-A01；等级 = P1；状态 = CONFIRMED。
- 标题 = 活跃 Streamlit 会话只核对用户版本，不复核当前 auth token 的撤销与有效期。
- 涉及文件 = `app.py`、`src/course2career/auth_service.py`、`src/course2career/user_repository.py`；具体函数 = 顶层认证恢复/刷新、`AuthService.refresh_principal` / `restore_session`；具体行号 = `app.py:199-262,287-301`、`auth_service.py:162-211`、`user_repository.py:174-214`。
- 触发条件 = 同一 opaque token 已由另一标签页 logout 撤销，或其 7 天有效期已过，但原 WebSocket 与 `st.session_state.principal` 仍存在并继续交互。
- 当前实际行为 = 新连接 `restore_session(token)` 正确拒绝；原连接每次 rerun 只执行 `refresh_principal(principal)`，该函数只读 `users.status/session_version`，不读 `auth_sessions.revoked_time/expires_time`。撤销单个 token 不改变 `session_version`。原连接可以继续以该 Principal 进入授权页面。
- 正确预期行为 = 每次受保护操作前，或至少每次已有登录态 rerun，服务端同时核验该 token 的撤销和到期；失败则清理 Principal 与浏览器 token。多标签页无需依赖刷新才能感知服务端撤销。
- 为什么此前测试没发现 = `tests/test_auth_sessions.py` 验证的是 `restore_session` 拒绝撤销/过期 token；没有“恢复后保持 WebSocket，再撤销/到期并 rerun”的用例。
- 生产是否可触发 = yes；SQLite 是否可复现 = yes；PostgreSQL 是否可复现 = 代码路径相同，未在本轮 PG 容器重放。
- 是否涉及：安全 = yes；数据 = yes（已有授权读）；费用 = yes（可能继续调用）；认证 = yes；并发 = yes（多标签页）；生产环境差异 = yes（浏览器/WebSocket 生命周期）。
- 最小复现 = 合成 SQLite：创建 session → `restore_session` 成功 → `revoke_session` → `restore_session` 为 `None`，但 `refresh_principal(原 Principal)` 仍成功；把创建时间设为 8 天前也得到相同分歧。本轮输出仅为布尔值：`True / False / True / False / True`。
- 建议修复方向 = 将当前 token 作为现有登录态的服务端验证条件，并在授权边界复核；不要只清理 localStorage 或仅依靠 `session_version`。保留 DB 故障时 fail closed。
- 建议新增回归测试 = 已打开 A/B 标签共享 token，A logout 后 B 下一次操作拒绝；活跃标签越过到期时间后拒绝；密码/版本轮换及 DB 不可用路径。
- 证据 = 上述调用路径、合成复现和 Streamlit 官方对 WebSocket/Session State 生命周期的[说明](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.session_state)。没有执行生产双标签测试。

### C2C-A02 — 一次额度预留不能约束 OpenAI 兼容 SDK 的实际 HTTP 尝试数

- ID = C2C-A02；等级 = P1；状态 = CONFIRMED。
- 标题 = System AI 的日额度/绝对熔断按逻辑预留计数，但默认 SDK 在可重试错误上最多尝试三次。
- 涉及文件 = `src/course2career/ui/analysis_page.py`、`access_services.py`、`llm_providers.py`、`llm_client.py`、`model_catalog.py`；具体函数 = `render_analysis_page`、`AIUsageService.start_call`、Provider 的 `_create_completion`；具体行号 = `analysis_page.py:304-380`、`llm_providers.py:175-180,260-273`、`llm_client.py:36-40`、`model_catalog.py:165-169`。
- 触发条件 = 平台 Provider 返回 408/409/429/5xx，或连接/读取超时；OpenAI SDK 采用默认 `max_retries=2`。DeepSeek 的受控 404 模型 fallback 还可能触发另一模型请求。
- 当前实际行为 = 一条 `api_usage` 已预留，SDK 可发三次 HTTP 请求；日志/计数只能看到一次逻辑调用。120/日绝对熔断不等价于 120 次实际 HTTP 请求；实际是否被 Provider 计费取决于其处理结果，**不能**由本轮推断。
- 正确预期行为 = 产品明确区分逻辑提交数与外部尝试数；若绝对熔断意图是实际请求数或费用边界，应对 SDK retry/fallback 建立相应的受控策略和审计计数。
- 为什么此前测试没发现 = 既有测试多用注入的假 SDK 检查解析/单次 fallback，生产 smoke 也只核对一条用量记录；未使用默认 SDK 对可重试 HTTP 状态进行计数。
- 生产是否可触发 = yes（满足可重试错误时）；SQLite 是否可复现 = yes（与 DB 方言无关）；PostgreSQL 是否可复现 = 与 DB 方言无关，未在本轮 PG 容器重放。
- 是否涉及：安全 = no；数据 = no；费用 = yes；认证 = no；并发 = no；生产环境差异 = yes（网络/Provider 错误）。
- 最小复现 = 本机 `openai==2.46.0`，用 `httpx.MockTransport` 对合成 Chat Completions 连续返回 500；一个 SDK `.create()` 调用触发 **3** 次传输，零真实网络。源码没有给生产 SDK 传 `max_retries`；验证脚本路径则显式传 `max_retries=0`。
- 建议修复方向 = 先决定熔断口径；若要一预留至多一次 generation，显式配置 `max_retries=0` 并单独审查 404 fallback；若保留重试，给尝试数独立上限和可观测计数。不要把一条 `api_usage` 描述成一次真实 HTTP。
- 建议新增回归测试 = MockTransport 的 500/429/超时与 404 fallback，断言实际尝试数、逻辑预留数、失败仍占额度及输出 token 限制。
- 证据 = 本机合成重试计数 3；OpenAI 官方库的[默认重试说明](https://github.com/openai/openai-python#retries)。[生产发布记录](c08-e1-production-release.md)已经诚实地把实际 HTTP 次数记为 UNKNOWN；本发现是现有费用熔断语义缺口，并非声称生产 smoke 重复计费。

### C2C-A03 — 退出登录未隔离同一标签页的未保存个人输入

- ID = C2C-A03；等级 = P1；状态 = HIGH_CONFIDENCE。
- 标题 = logout 清理报告对象，但仍持续渲染的课程上传、JD 和资料表单 widget 可能保留上一账号的输入。
- 涉及文件 = `app.py`、`src/course2career/ui/analysis_page.py`、`ui/candidate_profile_form.py`；具体函数 = sidebar logout、`render_analysis_page`、`render_candidate_profile_form`；具体行号 = `app.py:287-301,315-327`、`analysis_page.py:91-100,146-155`、`candidate_profile_form.py:95-130,152-200`。
- 触发条件 = A 在“个人分析”填写 JD/课程/项目资料，直接点 sidebar logout；相同 WebSocket 继续显示仍对 Guest 开放的“个人分析”，随后 B 在同一标签页登录。
- 当前实际行为 = logout 只 pop `principal/auth_session_token/job_analysis/analysis_report/legacy_analysis_report`；没有清理分析页 widget 输入。Streamlit 文档说明同一 widget 只要持续渲染就保留状态；最小 AppTest 验证 `text_area` 在同一会话的 logout + rerun 后仍显示合成 JD。完整 app 的 AppTest 导航每次回首页，无法据此宣称已在真实浏览器重放 A→B。
- 正确预期行为 = 身份切换时清掉上一主体的未保存敏感输入和分析页 widget 状态，或以身份边界隔离 widget；不应让下一位共享标签页用户看到 A 的 JD/经历。
- 为什么此前测试没发现 = 现有测试关注登录保持、登出后身份、报告对象清理；没有相同 WebSocket 的 A→Guest→B、仍在分析页的输入保留用例。
- 生产是否可触发 = unknown（框架语义与当前代码强烈支持，需真实浏览器同页验证）；SQLite 是否可复现 = 最小 Streamlit AppTest 可复现 widget 语义；PostgreSQL 是否可复现 = 与 DB 无关，完整路径未复现。
- 是否涉及：安全 = yes；数据 = yes；费用 = no；认证 = yes（身份隔离）；并发 = no；生产环境差异 = yes（浏览器 widget 状态）。
- 最小复现 = 最小 AppTest：同一页 `st.text_area` 写合成 JD → logout 只 pop Principal 并 `st.rerun()` → Principal 为 Guest，而 text_area 仍返回原文；无生产数据。完整 app 的 `st.navigation` AppTest 无法保留目标页，故本项保留 HIGH_CONFIDENCE。
- 建议修复方向 = 在 logout/账号切换边界清理敏感页面输入的 widget state，并对 Streamlit 自动生成 key 的 widget 制定可控重置方式；先做真实浏览器回归。
- 建议新增回归测试 = A 填写 JD、课程、项目/实习 → logout → 同页 Guest 和 B 均不见 A 数据；新标签页/刷新行为分别验证。
- 证据 = 当前 logout 列表、仍开放分析页，以及 Streamlit 官方[Widget 状态规则](https://docs.streamlit.io/develop/concepts/architecture/widget-behavior)；本机最小 AppTest `SET_VISIBLE=True / AFTER_LOGOUT_JD_VISIBLE=True`。

### C2C-A04 — CSV 技能导出保留可执行的电子表格公式前缀

- ID = C2C-A04；等级 = P2；状态 = CONFIRMED。
- 标题 = 不可信技能名/课程名写入 CSV 时没有按电子表格文本单元格处理。
- 涉及文件 = `src/course2career/report_exporter.py`、`ui/analysis_page.py`；具体函数 = `export_skill_matches_csv`、`render_adaptability_report`；具体行号 = `report_exporter.py:136-158`、`analysis_page.py:748-764`。
- 触发条件 = AI/人工确认的技能名或上传的课程名以 `=`、`+`、`-`、`@` 等公式触发字符开头，用户把导出 CSV 用 Excel/Calc 打开或分享。
- 当前实际行为 = `csv.writer` 仅做 CSV 语法转义；合成技能名 `=1+1` 在 UTF-8 BOM 后仍是首数据单元格的 `=1+1`。本报告没有打开电子表格执行公式。
- 正确预期行为 = 导出内容作为文本显示，不被表格程序解释为公式；保留用户输入可读性。
- 为什么此前测试没发现 = `tests/test_report_exporter.py` 只使用固定安全技能名并检查 BOM/表头。
- 生产是否可触发 = yes；SQLite 是否可复现 = yes；PostgreSQL 是否可复现 = 与 DB 无关。
- 是否涉及：安全 = yes；数据 = yes（导出文件）；费用 = no；认证 = no；并发 = no；生产环境差异 = no。
- 最小复现 = 构造合法 `AnalysisReport`，其中 `SkillMatch.skill_name='=1+1'`，调用 `export_skill_matches_csv`；首数据行以该前缀开头。
- 建议修复方向 = 在每个不可信 CSV 文本单元格做适合目标电子表格的公式防护；避免误伤数字得分，并评估保存后再打开的行为。
- 建议新增回归测试 = 技能/课程/JD 派生字段的公式前缀、引号/分隔符/换行以及正常中文文本。
- 证据 = 本机合成复现；OWASP [CSV Injection](https://community.owasp.org/attacks/CSV_Injection) 风险说明。

### C2C-A05 — 登录失败限流可通过重建 WebSocket 换 scope

- ID = C2C-A05；等级 = P2；状态 = CONFIRMED。
- 标题 = 登录限流键为瞬时 `guest_session_id`，刷新/新标签页即可从新计数桶尝试同一账号。
- 涉及文件 = `app.py`、`src/course2career/ui/auth_page.py`、`auth_service.py`、`user_repository.py`；具体函数 = Guest ID 初始化、登录表单、`AuthService.authenticate`；具体行号 = `app.py:238-239`、`auth_page.py:59-65`、`auth_service.py:124-160`、`user_repository.py:120-165`。
- 触发条件 = 对同一用户名在一个 WebSocket 尝试 5 次失败后刷新或新开标签页。
- 当前实际行为 = 新随机 scope 使 `count_recent_failed_logins` 查不到旧失败记录，下一次仍执行密码检查；旧 scope 才抛 `TooManyLoginAttemptsError`。这符合源码“同一浏览器会话”范围，却不能充当账号级暴力尝试防护。
- 正确预期行为 = 若产品把该机制作为公开登录防滥用保障，需能跨 WebSocket 维持合理的限流边界；不要把可重置 installation ID 当可靠身份。
- 为什么此前测试没发现 = `tests/test_auth_service.py` 的限流用例只在相同 `attempt_scope` 重复调用。
- 生产是否可触发 = yes；SQLite 是否可复现 = yes；PostgreSQL 是否可复现 = 代码路径相同，未在本轮 PG 容器重放。
- 是否涉及：安全 = yes；数据 = no；费用 = no；认证 = yes；并发 = yes（多连接）；生产环境差异 = yes（WebSocket 重建）。
- 最小复现 = 合成仓储对 scope A 累积 5 次后，第 6 次为 `TooManyLoginAttemptsError`；同一用户名改用 scope B 则仍走 `InvalidCredentialsError` 并新增失败记录。本轮无真实密码或账号。
- 建议修复方向 = 先明确公开登录的风险目标；如需要账号级保护，使用有界的账号维度/服务端节流并避免永久封号或用户枚举，同时保留统一错误消息。
- 建议新增回归测试 = F5/新标签页/并发 scope 的限流边界、正常用户误伤与窗口到期。
- 证据 = scope 初始化/查询键源码与合成计数 `A=5,B=1`；Streamlit 官方说明 reload 重建[WebSocket Session State](https://docs.streamlit.io/develop/api-reference/caching-and-state/st.session_state)。

### C2C-A06 — BYOK Key 与 Provider Profile 的保存不是同一事务

- ID = C2C-A06；等级 = P2；状态 = HIGH_CONFIDENCE。
- 标题 = 页面先替换加密 API Key，再保存模型/端点 Profile；后者失败会留下部分成功的配置。
- 涉及文件 = `src/course2career/ui/developer_page.py`、`api_key_service.py`、`provider_profile.py`、`product_repository.py`；具体函数 = `save_provider`、`save_key`、`ProviderProfileService.save`、两个独立 `upsert`；具体行号 = `developer_page.py:115-153`、`api_key_service.py:37-69`、`provider_profile.py:38-71`、`product_repository.py:473-495,547-570`。
- 触发条件 = 用户对已有 Provider 同时填写新 Key 与 Profile；Key upsert 已提交后，Profile upsert 因连接、约束或其他故障失败。
- 当前实际行为 = 每个 upsert 各自打开/提交连接，错误反馈出现时新 Key 已替换旧 Key，而旧 Profile 仍在；后续调用可能以不匹配的 Key/区域/模型发起，旧 Key 无法从应用恢复。正常校验成功路径无此问题。
- 正确预期行为 = “保存 Provider 配置”对 Key 与 Profile 要么一起生效，要么都不变；如刻意允许部分保存，则页面必须准确展示和恢复该状态。
- 为什么此前测试没发现 = APIKeyService、ProfileService 各自测试成功路径；缺少第二次写入故障注入与事务边界断言。
- 生产是否可触发 = yes（故障条件）；SQLite 是否可复现 = 依据独立提交确定，可用故障注入复现，本轮未运行完整 UI 故障注入；PostgreSQL 是否可复现 = 同一仓储边界，未在本轮 PG 容器重放。
- 是否涉及：安全 = no；数据 = yes；费用 = yes（错误 Key/端点尝试）；认证 = no；并发 = no；生产环境差异 = yes（DB 故障窗口）。
- 最小复现 = 合成已有 Key/Profile，令第二次 `upsert_provider_profile` 抛错；第一次 `upsert_api_key` 的 `with` 已独立提交。代码顺序和连接生命周期足以确定结果；仍建议真正的 SQLite/PG 故障注入。
- 建议修复方向 = 提供仓储级单事务保存配置，保留加密操作和权限复核；或让两项操作在 UI 中明确独立，不误报整体失败。不可通过在 UI 捕获异常后盲目回写旧明文 Key。
- 建议新增回归测试 = Profile 提交失败时旧 Key 的密文/元数据及旧 Profile 均不变；SQLite 与 PG 各测一次。
- 证据 = 四个函数的顺序与独立连接/commit；未触碰生产 Key。

### C2C-A07 — `.env.example` 按说明复制后会因管理员示例密码不足长度而停机

- ID = C2C-A07；等级 = P2；状态 = CONFIRMED。
- 标题 = 模板默认启用管理员引导配置，但示例密码不满足应用自己的 12 位下限。
- 涉及文件 = `.env.example`、`src/course2career/config.py`、`auth_service.py`、`app.py`、`docs/deployment.md`；具体函数 = `load_settings`、`_resolve_admin_password_hash`、管理员 bootstrap；具体行号 = `.env.example:52-56`、`config.py:68-70,151-154`、`auth_service.py:298-316`、`app.py:122-139`。
- 触发条件 = 按部署说明把 `.env.example` 复制为本地 `.env`，没有先更换管理员示例项就启动。
- 当前实际行为 = `ADMIN_USERNAME` 与 `ADMIN_PASSWORD` 非空，bootstrap 进入密码长度校验并抛 `AdminBootstrapError`；页面停止。另有模板 DeepSeek 旧模型默认值与代码当前 `deepseek-flash` 默认/两条 VERIFIED 精确模型状态不一致。
- 正确预期行为 = 未配置管理员的模板应可启动本地规则；需管理员时明确要求先填有效值。模型示例应与当期默认和认证边界一致，或标注为历史兼容而非当前推荐。
- 为什么此前测试没发现 = 测试构造设置或显式设置合成合格管理员密码，没有“照抄模板启动”的配置回归。
- 生产是否可触发 = no（当前生产配置由用户手工保存，未读取值）；SQLite 是否可复现 = yes（本地配置）；PostgreSQL 是否可复现 = 与 DB 方言无关。
- 是否涉及：安全 = no；数据 = no；费用 = no；认证 = yes（bootstrap）；并发 = no；生产环境差异 = yes（配置路径）。
- 最小复现 = 将模板的示例长度交给 `_resolve_admin_password_hash`，得到 `AdminBootstrapError`；未创建 `.env` 或输出任何真实密码。
- 建议修复方向 = 模板默认留空管理员项并写明首次初始化步骤；同步模型示例与生产/验证状态。
- 建议新增回归测试 = 用纯临时环境变量模拟模板默认值的启动配置，并断言不会触发管理员初始化失败；模型配置样例检查。
- 证据 = 模板、bootstrap 条件与合成长度校验。

### C2C-A08 — 发布后部署说明与部分 ADR 仍使用发布前状态和旧 TLS 口径

- ID = C2C-A08；等级 = P3；状态 = CONFIRMED。
- 标题 = 顶层发布记录已是 `RELEASE_READY=yes`，但部分面向后续维护者的文档仍称“未部署/生产用 SQLite”，并允许较低 TLS 模式。
- 涉及文件 = `docs/deployment.md`、`docs/decisions/003-*.md`、`005-*.md`、`006-*.md`、`007-production-postgresql-persistence.md`、`docs/ui-design.md`、`README.md`；具体函数 = 文档状态/部署契约；具体行号 = `deployment.md:1-4,65-106`、`decisions/007-production-postgresql-persistence.md:3,9-15`、`ui-design.md:64`、`README.md:55`。
- 触发条件 = 维护者按上述文档而非当前 README/E1 发布记录进行回退、部署或新环境配置。
- 当前实际行为 = ADR 007 仍写“尚未部署”、`sslmode=require/verify-ca` 可用、旧 Demo 数据迁移未决定；部署说明仍写 C08-D1 Draft 和线上 SQLite，部分 B 阶段 ADR 顶部写“生产未发布”。但生产代码只接受 `verify-full` 并用 `certifi.where()`，E1 发布记录明确 schema v4 与旧 Demo 不迁移。
- 正确预期行为 = 历史 ADR 决策内容可以保留，但其首页应有当前状态注记/指向后续决策；部署手册应以现行生产契约为准，不给出旧 TLS/回退指令。
- 为什么此前测试没发现 = 文档检查未校验跨文件时间状态与当前 `DatabaseBackend` 策略。
- 生产是否可触发 = yes（人工按旧说明操作时；运行时代码仍 fail closed）；SQLite 是否可复现 = 不适用；PostgreSQL 是否可复现 = 不适用。
- 是否涉及：安全 = yes（操作说明风险，代码未降级）；数据 = yes（迁移/回退误导）；费用 = no；认证 = no；并发 = no；生产环境差异 = yes。
- 最小复现 = 对照上述文档与 `database_backend.py:278-307`、`docs/c08-e1-production-release.md:5-30`；无需运行或改配置。
- 建议修复方向 = 经本审计确认后做文档状态清理，保留 ADR 历史原文但加“后续实施状态/已被更严格配置取代”提示；更新部署运行手册。
- 建议新增回归测试 = 轻量文档链接和关键发布状态一致性检查；不要把所有历史日志中的“当时未发布”误改为当前状态。
- 证据 = 本地当前文档与源码；GitHub main SHA/CI 只读核对。

## 15 项审计覆盖与排除结论

| 领域 | 结论与边界 |
| --- | --- |
| 1 登录持久化 | PENDING→TOKEN/NO_TOKEN 状态区分已有测试；发现 C2C-A01/A03。生产 F5 smoke 是历史人工 PASS，本轮未重测。 |
| 2 dict_row | 当前多列 aggregate `admin_overview` 均有唯一 alias 且按名取值；其余整数下标在已检索仓储查询中为单列 `COUNT/MAX`。`SELECT *` 只针对单表。**未发现**本轮可确认的重复列名/错位新 bug。psycopg [dict_row 以列名为键](https://www.psycopg.org/psycopg3/docs/api/rows.html)。 |
| 3 双后端 | PostgreSQL 适配器把 `IS ?` 映射为 `IS NOT DISTINCT FROM %s`，`BEGIN IMMEDIATE` 映射事务 advisory lock；迁移/最终槽位已有 PG CI。业务时间以 UTC ISO 文本保存、按东八区求日界，当前写入路径一致。新发现未在 PG 本机复现；无证据声称全方言覆盖。 |
| 4 TLS/网络 | production `require_verified_tls=True`，显式 `sslmode=verify-full` + `certifi.where()`；`httpx`/SDK 使用默认验证，受控端点关闭重定向。未发现降级路径。DNS/IPv6/代理失败情形未经 Cloud 现场重演；文档旧 TLS 口径见 C2C-A08。 |
| 5 Provider 副作用 | 本地 System 选择验证→原子预留→Provider factory/model discovery→generation，顺序正确。目录读取可在预留后发生、失败也占一次额度，符合既定失败不退款口径；可重试 HTTP 次数超出逻辑熔断口径见 C2C-A02。超时后**用户再次点击**仍会新增一条预留，这是独立逻辑提交，当前没有请求幂等键；是否要去重取决于产品契约，未作为已证实 bug。BYOK/System Key 读取路径分离。 |
| 6 Streamlit rerun | 按钮写入只在瞬时 True 分支；没有发现自动 rerun 重复生成的确定路径。组件首次空值与 PENDING 被区分；logout widget 隔离风险见 C2C-A03。多标签页需真实浏览器补测。 |
| 7 认证/session | 32 字节 CSPRNG opaque token、数据库只存 SHA-256、恢复时读取最新用户角色/Plan/状态/版本；版本变化使旧 session 失效。单 token revoke/到期在已有 WebSocket 上不生效见 C2C-A01；登录限流 scope 可刷新见 C2C-A05。旧测试账号事件仍为 contained，不把账号写成 disabled。 |
| 8 Turnstile/注册 | 服务端 Siteverify、精确 hostname/action 校验，失败关闭注册；验证后才进入原子注册事务；哈希来源和成功窗口受锁保护。Cloudflare [token 单次使用且 300 秒过期](https://developers.cloudflare.com/turnstile/get-started/server-side-validation/)；此限制由服务端验证，不由客户端独自判断。未发真实挑战。本轮未发现确定的重复注册槽位绕过。 |
| 9 System quota | 既有 SQLite 边界测试覆盖 Guest/Free/Pro/Developer/Admin、100/120、东八区午夜、失败仍计数；PG CI 最终槽位测试成功。每条逻辑请求一条预留不等于实际 HTTP 次数，见 C2C-A02。installation ID 本来可被客户端重置，设计文档已明示，不当作可靠身份凭据。 |
| 10 schema/rollback | v4 additive migration 在 PG advisory 事务中执行，版本记录在 DDL 后，fallback 分支已保留；本轮未改/运行 fallback。`pre-v4 main` 不可部署到 v4 库。新 migration 故障/锁表时长未在本机 PG 重测；不能以 CI PASS 代替生产恢复演练。 |
| 11 Secret/log | 当前跟踪文件模式扫描只命中 `.env.example`、CI、部署示例、合成测试的占位串；没有把候选字符串输出到报告。数据库启动日志只打印固定类别/类型；auth 恢复日志只打印状态/布尔；`Settings` 的 API Key、DB URL、主密钥、Turnstile Secret 等字段设置 `repr=False`。没有证据证明历史工具日志从未泄露，事件保持 contained。未审计平台日志全量/历史 Git blob。 |
| 12 原子性 | 注册和 System quota 的 check+insert 同一 DB 事务/锁；BYOK 组合保存跨两个提交见 C2C-A06。报告插入单语句；管理员变更以单条 UPDATE 加版本旋转。 |
| 13 客户端信任/XSS | localStorage token 仍受既有 JS 可读限制；服务端从 DB 还原权限，不信任 installation ID 为身份。`unsafe_allow_html` 仅在静态主页/样式使用，未见把 JD 拼入不安全 HTML。CSV 二次打开风险见 C2C-A04。 |
| 14 文件/导出/输入 | 上传组件限 5 MB `.xlsx`，解析后用 Pydantic 校验；并非解压后的内存硬上限，压缩炸弹/资源耗尽未以真实文件复现，不列 confirmed。CSV 已复现 C2C-A04；导出文件名是固定常量，未见路径遍历。 |
| 15 配置/状态漂移 | `.env.example` 的管理员引导故障见 C2C-A07；旧部署/ADR 状态见 C2C-A08。根级 Secret 值未读取，不推断其现值。 |

## 同类缺陷对应关系

| 模式 | 结果 |
| --- | --- |
| SIMILAR_TO_LOGIN_PERSISTENCE | found: C2C-A01, C2C-A03 |
| SIMILAR_TO_DICT_ROW | none |
| SIMILAR_TO_TLS_PORTABILITY | none；旧 TLS 文档口径见 C2C-A08 |
| SIMILAR_TO_SQLITE_POSTGRES_DIFF | none confirmed；PG 新场景未重放 |
| SIMILAR_TO_PROVIDER_RETRY_FALLBACK | found: C2C-A02 |
| SIMILAR_TO_QUOTA_ATOMICITY | found: C2C-A02（HTTP 尝试数口径）；预留的 DB 原子性未发现新缺陷 |
| SIMILAR_TO_SECRET_LEAK | none confirmed；历史测试账号事件为 contained，不能称“从未发生” |
| SIMILAR_TO_STREAMLIT_RERUN | found: C2C-A01, C2C-A03, C2C-A05 |
| SIMILAR_TO_SCHEMA_ROLLBACK | none；现行 fallback 与禁止部署 pre-v4 主线需继续保留 |
| SIMILAR_TO_STATUS_DRIFT | found: C2C-A07, C2C-A08 |

## 未列为 bug 的重要观察

- Auto-Safe 默认候选可能包括当前 `verified_models.json` 未精确认证的历史兼容模型。合成目录与假 SDK 可走 404→备用模型，但 [README](../README.md) 已明确“白名单不等于 C08-B2 当前真实验证状态”；它是显式产品边界。管理员页的“已验证优先顺序”措辞可以随状态文档清理再核对，不把未经认证直接等同漏洞。
- PostgreSQL `dict_row` 仍可被错误的重复 alias 损坏，但当前生产仓储查询没有发现该结构；不能仅因 `_Row` 支持整数索引就复报旧事故。
- SQLite `Connection` 的 `with` 不自动 close，本机合成临时库在 Windows 退出时出现文件占用；这是本地资源生命周期问题，生产 PostgreSQL 的 `PostgresConnection.__exit__` 会 close。本轮未将其列为“生产同类缺陷”。Python [sqlite3 context manager 说明](https://docs.python.org/3/library/sqlite3.html#how-to-use-the-connection-context-manager)。

## 建议处理顺序与运行判断

1. 先在隔离分支修 C2C-A01，并用真实浏览器双标签/logout/到期及 SQLite+PG 回归；同时真实浏览器核验 C2C-A03，再确定是否合并处理身份切换的输入清理。当前不能把 logout 当成“已有所有标签立即失效”。
2. 与产品所有者明确 System AI **逻辑调用**或**真实 HTTP 尝试**的熔断承诺，再处理 C2C-A02；在此之前保留现有 100/120 逻辑硬上限并监测 Provider 账单，不声称绝对货币上限。
3. 之后处理 C2C-A04/A05/A06；配置与文档 C2C-A07/A08 可单独小批量修正。每项均需独立授权，本报告没有修改代码或提交。

`PRODUCTION_IMMEDIATE_ACTION_REQUIRED=yes`：需要立即告知维护者 A01 的撤销边界，评估活跃共享标签/管理员会话风险并安排修复；这不等于本轮执行生产变更。`SAFE_TO_KEEP_PRODUCTION_RUNNING=no`（按完整安全会话语义判断）：在 A01 被修复并确认前，不能将当前应用称为满足“logout 后所有活跃会话立即失效”。本报告没有发现 P0 或已证实的生产数据/费用失控；若运营方接受这个短期限制，可另作风险接受决策。
