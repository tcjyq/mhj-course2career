# Provider 访问与精确身份实施报告

日期：2026-10-05（东八区）。独立候选，未 merge / deploy。BASE=526faf920eba68634d58be75504e3140235c3414；BRANCH=fix/provider-model-identity-verification。原工作区分支及四个未跟踪文件保留，未读取主密钥文档。

## 1. PI DESIGN ADOPTED

实际读取 [Pi README](https://github.com/earendil-works/pi/blob/200387122ca450d6387f033949423114a270b96c/packages/ai/README.md) 的 Supported Providers、Provider Factories/ownership、Querying/Static/Dynamic Catalog、Auth resolution/store/env、Error/Abort、createProvider、OpenAI compatibility、Faux、OAuth/programmatic 部分，以及相应 providers/auth/api/models/retry/test 源码。重新核对 main 仍为 `200387122ca450d6387f033949423114a270b96c`；[MIT LICENSE](https://github.com/earendil-works/pi/blob/200387122ca450d6387f033949423114a270b96c/LICENSE)。未复制非 trivial 实现，未添加 Pi 或其他依赖。

| PI PATTERN | C2C ADAPTATION | WHY ADOPTED | WHY NOT COPIED DIRECTLY |
|---|---|---|---|
| Provider ownership / protocol separation | 原 ProviderPreset 升级为访问声明来源，adapter 按现有 protocol 实现 | 统一端点/auth/catalog/兼容事实 | C2C 只有十家与 JobAnalysis，不需要 Models collection/agent SDK |
| Typed credential resolution | AccessMode / CredentialKind 独立，Resolver 使用 APIKeyService | 用户失败不能静默用平台 Key；所有权不等于 auth type | Pi provider-only credential store 不符合 C2C 多账户数据库隔离 |
| Explicit catalog refresh | peek/read/resolve 纯缓存，refresh 显式联网 | 避免 render/工厂隐藏 Provider 请求 | 保留现有 TTL、Key-version、snapshot 和 UI，不另建 catalog 系统 |
| Compatibility declaration | 显式 MiniMax reasoning_split、DeepSeek thinking、Bailian schema 前缀、OpenRouter strict 路由、Gemini modelVersion | 相同 wire family 仍有具体差异 | 不复制 URL guessing、未使用的参数或 speculative aliases |
| Normalized results / bounded errors | JobAnalysis + usage + trace + CallEvidence；固定错误文案与 attempt budget | 明确契约、身份和实际尝试 | 不引入流式事件、abort/retry 通用框架，现有请求 timeout 保留 |
| Faux testing | tests/faux_provider.py scripted wire + 实际 SDK MockTransport | 离线反证而非真实 Key 调试 | 只是测试辅助，不是新的产品 Provider、模拟计费或生成模型 |
| OAuth/access semantics | 预留 enum，当前仅 API 启用 | 以后可表示同品牌不同访问产品 | 不复制固定 client ID、IDE header、私有 endpoint 或未完成 OAuth |

## 2. TARGET ARCHITECTURE IMPLEMENTED

ProviderPreset → API AccessDefinition（品牌/协议/官方区域端点/auth/discovery/schema/reasoning/usage/compatibility）→ CredentialResolver → APIKeyService 的当前用户加密 Key → 最后已知目录与模型解析 → 五条协议 adapter → JobAnalysis + LLMUsage + immutable ModelTrace + ProviderCallResult → 分层连接 / 固定集认证。

`key_mode=user/system` 继续表示 credential/quota 所有权。`extract_job_skills()` 返回 JobAnalysis 的旧契约保留，`last_result` 增加统一结果；没有通用聊天层或数据库迁移。仅 runtime trace；显式验证脚本会将安全 trace 写入本地证据 JSON，不写业务历史数据库。

## 3. CHANGED FILES

| File | Why |
|---|---|
| src/course2career/provider_access.py | 新访问与凭证类型、加密后端 Resolver、失效检查、无 user→system fallback |
| src/course2career/provider_runtime.py | 不可变 attempts/trace、有限预算、统一结构化调用结果；不含 Secret/JD |
| src/course2career/provider_registry.py | 在原预设上新增 AccessDefinition 与显式兼容配置，不改品牌/端点/默认模型 |
| src/course2career/provider_factory.py | 敏感建 client 时用 Resolver；仅开放 API；传递 saved DeepSeek 模型，SDK retry 0 |
| src/course2career/llm_provider.py | 接口声明 last_trace/last_result；说明 usage.model 只是兼容账目标签 |
| src/course2career/llm_client.py | Responses 先采集 raw model/usage 再 SDK 解析；端点取受控声明，防 SDK ambient base URL 覆盖 |
| src/course2career/llm_providers.py | Chat/DeepSeek 真实返回身份、逐次 fallback、reset/错误记录，兼容参数来自声明 |
| src/course2career/native_providers.py | Anthropic model / Gemini modelVersion 独立 trace，失败也保留已收到元数据 |
| src/course2career/model_catalog.py | DeepSeek read/resolve 不联网、显式 refresh，原白名单与偏好顺序保留 |
| src/course2career/model_discovery.py | 目录键包含 API mode，refresh 经 Resolver，保留 render view 与 Key-version 隔离 |
| src/course2career/provider_connection.py | 六层连接证据、真实返回与 MATCH/MISMATCH/UNKNOWN，不升级单次 VERIFIED |
| src/course2career/provider_validation.py | 认证只信逐次 trace，保留失败 trace，用实际 attempts 统计外发；身份未知不套目标费率 |
| src/course2career/provider_verification.py | 新 v1 认证强校验、旧记录显式 v0、禁止新增 legacy VERIFIED，安全 JSON round trip |
| src/course2career/provider_error_classification.py | 安全 HTTP/SDK code 分类，区分套餐、额度、服务不可用；不读敏感错误正文 |
| src/course2career/ui/developer_page.py | API 模式、实现认证/最近凭证测试分离、Key-version 绑定最近状态与身份文案 |
| tests/faux_provider.py | 可脚本化 success/auth/404/429/schema/timeout/mismatch/missing usage 的测试 wire |
| tests/test_provider_model_identity.py | 两项先失败的原 bug 回归，不允许 usage 显示标签冒充返回证据 |
| tests/test_provider_access_runtime.py | 十家贯通、五协议、身份/预算/fallback/credential/isolation/legacy/error 分层测试 |
| tests/test_llm_client.py | 实际 SDK 离线 schema failure 保留 model/usage；固定 endpoint 不受环境覆盖 |
| tests/test_model_catalog.py | 新纯读取与显式刷新语义、保留 stale 和偏好选择回归 |
| tests/test_c08_b2.py | 测试认证 fixture 明确提供 genuine fake trace，适配新严格记录与错误分类 |
| README.md | 候选能力与未部署边界 |
| docs/requirements.md | 新访问/身份/认证验收要求 |
| docs/architecture.md | 新调用链、Secret 与运行时生命周期边界 |
| docs/user-guide.md | 卡片标签、身份 UNKNOWN、显式刷新及 BYOK 不自动重放说明 |
| docs/ui-design.md | 卡片状态语义及合成截图 |
| docs/evaluation.md | 新验证与可比性能证据 |
| docs/development-log.md | 当前实施、独立审查修正与范围记录 |
| docs/c08-multi-provider-design.md | 原预设增量演进，预留与实现分开 |
| docs/c08-provider-validation.md | LEGACY_MODEL_IDENTITY_EVIDENCE_LIMITATION 与 v1 规则 |
| docs/c08-model-discovery.md | read/refresh/cache/access 语义 |
| docs/c08-provider-matrix.md | 十家当前离线状态，旧表保留为历史快照 |
| docs/decisions/009-provider-access-and-runtime-identity.md | 增量架构决策，不删除旧 ADR |
| docs/provider-access-upgrade-20261005.md | 本完整报告 |
| docs/provider-access/20261005/benchmark-summary.json | 三次 warm 样本与相同口径前后汇总 |
| docs/provider-access/20261005/before-warm-actions.json | 精确 main 的本地原始动作结果 |
| docs/provider-access/20261005/after-warm-actions.json | 候选分支本地原始动作结果 |
| docs/provider-access/20261005/security-browser.json | 七组本地浏览器回归结果 |
| screenshots/provider-access-synthetic-20261005.png | 假账号/假 Key 的卡片截图，不是生产认证 |

## 4. MODEL IDENTITY

SAVED=保存/传入的模型配置（如 deepseek-flash）；RESOLVED=本轮解析主模型（如 auto_safe 选 deepseek-v4-pro）；REQUESTED=每个实际 attempt 的 model；RETURNED=供应商真实 model/modelVersion，缺失 None/UNKNOWN，陌生值原样保留，不截断为可匹配的 ID；DISPLAYED=兼容账目展示标签。

MATCH 只表示最后一尝试 raw returned == requested；不保证整个验证目标被认证。固定认证要求每次尝试成功且请求、真实返回均等于最初目标，因而 A→404→B 即使 B MATCH，也不能认证 A 或把 fallback 混入精确固定集。没有新 alias 规则，未经受控且有日期的关系不推断别名。`LLMUsage.model` 可保留请求标签兼容旧账目，但验证器从不使用该字段当 raw 证据。trace 每次调用 reset，失败不会复用上次成功。

## 5. PROVIDER MATRIX

| Provider | API protocol | Offline access/factory/adapter/trace | New real verification |
|---|---|---|---|
| DeepSeek | Chat JSON object + 原404 fallback | PASS | 未执行；旧2026-09-26认证保留/legacy限制 |
| Bailian | Chat，原 Qwen 前缀 strict 策略 | PASS | 未执行；旧北京qwen3.8-flash认证保留/legacy限制 |
| SiliconFlow | Chat prompt JSON | PASS | UNVERIFIED |
| Moonshot | Chat prompt JSON / 静态目录 | PASS | UNVERIFIED |
| Zhipu / GLM | Chat prompt JSON / 静态目录 | PASS | UNVERIFIED |
| MiniMax | Chat prompt JSON + reasoning_split | PASS | UNVERIFIED |
| OpenAI | Responses strict parse，先 raw 元数据 | PASS | UNVERIFIED |
| Anthropic | Native Messages / model | PASS | UNVERIFIED |
| Gemini | Native generateContent / modelVersion | PASS | UNVERIFIED |
| OpenRouter | Chat，strict需原精确 metadata/认证证据 | PASS；prompt fixture不升级VERIFIED | UNVERIFIED |

PASS 全是本机确定性测试，不是十家真实账户兼容性。默认模型、端点、pricing、System AI quota 未变化；verified_models.json 未改写。

## 6. ACCESS MODE

API=implemented，CredentialKind.API_KEY 经现有加密 Key 路线。PLAN/OAUTH_SUBSCRIPTION=reserved, disabled；PLAN_KEY/OAUTH=type-only。枚举存在不表示凭证流程可用，未实施模式在读取 Secret/网络前拒绝；OAuth 类型不自动表示 subscription。

## 7. SUBSCRIPTION

SUBSCRIPTION_IMPLEMENTED=no。这里不是“所有候选四项许可都失败”：Copilot 的官方文档明确支持 SaaS、多用户和服务端；但完整安全 OAuth、每用户 runtime 生命周期、Streamlit Cloud 适配与 JobAnalysis fixture 证明尚未实施，超出本次安全的小 PR，按用户 OAuth 停止条件保留后续。没有开放一个未经完成验证的选项。

| Candidate | Official Gate evidence | Decision |
|---|---|---|
| MiniMax Token Plan | [官方 overview](https://platform.minimax.io/docs/token-plan/intro)扩大到创意应用，但没有明确证明 C2C 独立公网多租户服务端代持 Key 的许可；Subscription Key 不等于 PAYG Key | HOLD，不能推断 server/multiuser 许可 |
| GitHub Copilot SDK | [官方多租户/服务端指南](https://docs.github.com/en/copilot/how-tos/copilot-sdk/setup/multi-tenancy)明确 SaaS、empty mode、每 session 用户 auth 与 runtime 隔离 | 四许可门可通过；小范围安全实施与实际 JobAnalysis gate 未通过，DEFER |
| OpenAI Sign in with ChatGPT | [官方 plan usage](https://developers.openai.com/siwc/token-sharing-open-source)当前针对 OSS/local；remote hosted 需 interest/批准路径 | HOLD；不把 Plus 永久等同于不能用API，也不推断远程许可 |
| Kimi For Coding | [官方概览](https://www.kimi.com/code/docs/en/)允许 Key 接第三方开发工具，未明确 C2C 非编码公网多用户后端 | HOLD |
| Qwen Token/Coding Plan | [官方规则](https://help.aliyun.com/en/model-studio/coding-plan)限制交互式编程工具，禁止自定义应用后端 | REJECT 当前 C2C 模式 |
| ZAI Coding Plan global | [官方 usage policy](https://docs.z.ai/devpack/usage-policy)限制官方支持产品，不推广到自建 C2C；中国区不能机械套全球规则 | REJECT global 接入；不声称中国区许可 |
| MiMo Token Plan | [官方订阅页](https://mimo.mi.com/docs/en-US/tokenplan/Token%20Plan/subscription)明确禁止 non-coding 自动脚本/自定义后端；通用路径无正文后已找到并读取当前 en-US 官方页 | REJECT 当前 C2C 模式 |
| Claude consumer OAuth | [官方 auth 限制](https://code.claude.com/docs/en/legal-and-compliance)禁止第三方提供Claude.ai登录/代转消费者凭证；托管未修改Claude Code例外不是C2C adapter | REJECT |

这些是读取公开文档后的范围判断，不是套餐/账户实测。无共享订阅、Cookie、私有 backend API、固定 client ID 或 IDE 伪装。

## 8. VERIFICATION

IMPLEMENTATION_VERIFICATION=端点/精确模型的历史固定集；CURRENT_CREDENTIAL_STATUS=此用户/端点/模型/Key版本最近一次测试。auth/request/schema/JobAnalysis/usage/model_match 分别表达，不互相替代。单次测试最多 Schema-compatible；缺返回为 UNKNOWN、陌生返回为 MISMATCH，仍可有合法 JobAnalysis。

LEGACY_MODEL_IDENTITY_EVIDENCE_LIMITATION：旧适配器可将请求模型填进 usage.model，因此旧记录 returned_model 不能重解释为 raw 响应证明。保留两条历史数据，UI 显式标注，不 blanket invalidation。新记录默认 v1，缺trace不能 VERIFIED；loader仅旧缺字段行显式v0，save_record拒绝新legacy VERIFIED。

## 9. ERROR / RETRY

沿用 AUTH_ERROR/MODEL_NOT_FOUND/RATE_LIMIT/TIMEOUT/SCHEMA_UNSUPPORTED/SCHEMA_VALIDATION_FAILED/NETWORK_ERROR/UNKNOWN_ERROR 等兼容名字；新增 MODEL_NOT_INCLUDED/USAGE_LIMIT/QUOTA_EXHAUSTED/PROVIDER_UNAVAILABLE。只检查 HTTP 状态、异常类型和 allowlist SDK code，不读异常正文或 Provider body。普通400不再凭schema参数猜SCHEMA_UNSUPPORTED；只有明确受支持的错误码才分类。无法确认时保持UNKNOWN/PROVIDER_ERROR。

System 和 BYOK SDK retry 均为0；每次业务调用预算1，已有 DeepSeek 404 fallback最多2。不新增通用 transient retry，也不因为 schema、mismatch、quota、subscription limit换模型重放。异常 trace 只保留安全code，不含原消息；实际尝试计数包括fallback。

## 10. TESTS

独立审查反证后修正三项：实际SDK提前解析、fallback次数、legacy默认旁路；相应回归已加入。首先两项原bug测试真实FAIL（旧实现误给VERIFIED），修复后PASS。

最终命令使用项目 .venv 的 Python 3.12、PYTHONPATH 中本机已安装 pool 依赖；没有安装/升级项目依赖。所有 DB URL 强制 localhost:55448 的独立合成库。

- `python -m pytest -p no:cacheprovider --basetemp D:/codex_study/_tmp/c2c-provider-20261004/full-submission`：带本机PG，全量423 passed、1 skipped，79.26s。唯一跳过为未在全量进程设置恢复目标，已在下面独立恢复校验补齐。
- `python -m pytest -m postgres ...`：13 passed。
- `pg_dump --format=custom` → 独立 restored DB `pg_restore --exit-on-error` → `pytest -m postgres_restore ...`：1 passed，补齐 restore 环境跳过项。
- `python -m ruff check .`：PASS；`python -m ruff format --check .`：PASS，113 files already formatted；`git diff --check`：PASS。
- `node scripts/verify_performance_browser.cjs`（local only）七组 PASS：Guest deep link、18次普通导航单轮/无残留、登录deep link/F5/new tab、A→Guest→B、BYOK禁用再启用、双标签logout、invalid token。
- 同PR7的本地 instrumentation + browser actions：规则演示和历史/UI正常，三用户场景、每项三次warm，external Provider attempts=0。
- 最终源代码本地 UI 复测：十张已配置卡片、新实现认证文案、本地规则、logout PASS；截图已更新。临时 Playwright 脚本等待规则结果元素后通过，未修改产品代码或读取真实凭证。

不靠 test doubles 假装真实认证；REAL_AI_CALLS=0。生产 credential/Secrets/DB 未读取。

## 11. PERFORMANCE REGRESSION

本轮重新归档精确 main 和候选，用相同本机 PostgreSQL 18.6、Python3.12/Streamlit1.60/psycopg3.3.2/pool3.3.3/Chromium、同一合成账号与口径。SQL只计 repository显式语句，另列 checkout/health check；connect指物理建连，0仅warm不是0 DB round trip。ms为完成Python执行耗时，不等于浏览器等待或生产延迟。

| Scenario | SQL before→after | Checkout before→after | New physical connect | Runs | Python median ms before→after | Delta ms |
|---|---|---|---|---|---|---:|
| BYOK Developer | 8→8 | 8→8 | 0→0 | 1→1 | 153.04→154.53 | +1.49 |
| BYOK Analysis | 7→7 | 7→7 | 0→0 | 1→1 | 135.21→143.33 | +8.12 |
| BYOK quota | 4→4 | 4→4 | 0→0 | 1→1 | 31.46→38.77 | +7.31 |
| BYOK membership | 4→4 | 4→4 | 0→0 | 1→1 | 34.11→40.78 | +6.67 |
| BYOK local rules | 7→7 | 7→7 | 0→0 | 1→1 | 220.94→226.89 | +5.95 |

每项3个原始Python/browser样本及health次数见[summary](provider-access/20261005/benchmark-summary.json)、[before](provider-access/20261005/before-warm-actions.json)、[after](provider-access/20261005/after-warm-actions.json)。结构性能回归=PASS：没有几十次SQL、自动ProviderHTTP或普通双rerun。耗时有1–8ms变化和范围重叠；三样本不足以声称统计上无回归或提速。F5/login/storage handshake仍允许必要额外轮次。没有追求进一步提速，也没有生产before/after证据。

## 12. SECURITY

ACCOUNT_ISOLATION=PASS；BYOK_DISABLE=PASS；SESSION_REVOKE=PASS；KEY_ROTATION=PASS；CREDENTIAL_LEAK=PASS，均限本地确定性/合成浏览器范围。原 app 入口每轮 session 复核、敏感保存 callback session-token复核、ProviderDisplayView的owner/render边界与Key-version失效保持。Resolver不收display view，不缓存Secret，不fallback平台凭证；关闭BYOK后旧Principal不能读取Secret；双标签logout下一动作拒绝。静止标签上次DOM不是主动推送实时撤销，保持原边界。

没有 OAuth 数据、schema migration、用户/会员/注册/Turnstile/pricing/quota/评分算法改变。客户端在当次敏感动作创建，不跨rerun缓存；即时校验到外发之间仍存在通常的在途竞态，不声称已取消在途HTTP。日志/error/trace不记录Key/JD/Provider正文，截图只用假账号和假Key。

## 13. PR

独立分支 `fix/provider-model-identity-verification`，基于最新确认main `526faf920eba68634d58be75504e3140235c3414`。最终HEAD、Draft PR URL和精确HEAD的CI结果在交付中记录。RELEASE_READY=no，PRODUCTION_UNVERIFIED；本轮只commit/push/Draft，不mark ready/merge/deploy。

REAL_VALIDATION_REQUIRED：若要更新真实精确认证，另行授权 DeepSeek global/deepseek-flash 和 Bailian cn-beijing/qwen3.8-flash 各连接1+固定题4（共10次推理）；Bailian需合法区域/Workspace参数。成本需按当时价格与实际usage核算，目前未执行，不能写0成本。其余Provider需先指定精确model、合法用户Key、expected calls/cost，不批量读生产Key。

## 14. NEXT ACTION

REVIEW_PR
