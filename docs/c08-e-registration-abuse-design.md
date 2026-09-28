# C08-E 注册防滥用与平台 AI 额度设计（E1 已发布）

设计日期：2026-09-27；生产发布：2026-09-28。设计经人工审核，最终决策以本节及 [ADR 008](decisions/008-registration-abuse-and-system-ai-fuses.md) 为准。生产 PostgreSQL 与持久登录已获验收，`AUTH_SESSION_PERSISTENCE_READY=yes`。Cloudflare 生产 Turnstile widget 与精确 hostname `mhj-course2career.streamlit.app` 已获验证；两项 Turnstile Secret 名称对应的值由用户人工保存到 Streamlit Secrets，本项目文档不记录其值。E1 已合入 main，schema v4、真实注册及一次逻辑 System DeepSeek 生产 smoke 均通过，`RELEASE_READY=yes`；证据、测试账号凭证事件及未执行的旧路径手工回归见[生产发布记录](c08-e1-production-release.md)。

## 已批准的最终口径

- Guest 2/会话/日、Free 5/用户/日、Pro/Developer 套餐 20/用户/日；Developer Mode 不提升 System AI 额度。`public_free` installation 池 10/日，`assigned_20` 池 20/日，Admin 不受产品额度限制但受绝对熔断限制；BYOK 独立。
- 非 Admin System Key 全站 100/东八区自然日；含 Admin 的全部 System Key 绝对 120/日；与其他额度在同一预留事务核对。System AI 单次输出上限 4096 tokens，已有更低限制继续生效。
- 用量哈希 8 天、注册来源哈希 30 天后逻辑失效。到期后不再参与风控识别，并在后续相关写事务中清除；不引入 scheduler，也不承诺精确物理删除。
- 邮箱验证推迟到 E2；E1 不加邮箱字段、邮件服务或 Secret。生产 Turnstile 配置与真实浏览器注册 smoke 已通过；这不证明 Turnstile 能阻止所有人工或设备切换滥用。

## 决策与边界

目标是降低自动与真人批量注册的收益，并给平台补贴的 System AI 增加跨账号的当日上限；**不能证明“一人一号”**。注册须通过 Turnstile，成功注册按 installation 限制为滚动 24 小时最多 2 个、滚动 7 天最多 3 个。Free 用户原有 5 次/东八区自然日额度不变，同一 installation 的 Free/Guest System AI 共用 10 次/日；Guest 原有每匿名会话 2 次也保留。已登录用户的本地规则与 BYOK 不受此平台补贴额度限制。旧账号登录和管理员登录不要求补做注册验证。

现有 [权限表](access-control.md) 给 Pro/Developer 20 次/日、Admin 无产品级用户额度。Pro/Developer 使用同 installation、同类账户共享的 20 次/日池；Admin 不进入公开补贴池，但受绝对安全熔断。Free/Guest 的 10 次池不因同设备出现 Pro 账户而增加。`quota_class` 在每次预留时固定为 `public_free`、`assigned_20` 或 `admin`，不事后按当前 Plan 重算。

Turnstile 与 installation 限额只提高攻击成本，攻击者仍可清浏览器数据、伪造随机 ID、换设备或人工解题。非 Admin 公开补贴上限已定为 100/日，所有 System Key 含 Admin 的绝对熔断为 120/日，并保留单次输出 token 上限。调用数有硬边界，但币种和价格可能变化，不能称为精确货币支出上限。

## A. Turnstile 注册门槛

只在公开注册表单挂载 Turnstile。建议在现有 Streamlit 1.60 first-party component 的独立实例中显式渲染 Managed widget，限定 `action=register`；组件只把挑战 token 交给当前 Python 会话，绝不写入 localStorage、URL、日志或数据库。组件就绪前不可提交注册，失败或到期时重置 widget 并提示重试。不要把认证 session token、installation ID 和 Turnstile token 混入同一状态键。Streamlit Community Cloud 的 iframe、CSP、组件 rerun 与大陆网络可达性必须在本地真实浏览器及上线前预览环境验证，不能只凭组件文档认定可用。[Cloudflare 显式渲染说明](https://developers.cloudflare.com/turnstile/get-started/client-side-rendering/)；[Streamlit 1.60 V2 组件接口](https://docs.streamlit.io/1.60.0/develop/api-reference/custom-components/st.components.v2.component)。

服务端在任何 `users` 插入前，以固定超时 POST 到 Cloudflare Siteverify。只有 `success=true`、`hostname` 精确属于生产 allowlist、`action=register`，才进入注册事务；无 token、过长 token、错误主机/action、验证失败、超时、非预期响应或缺 `TURNSTILE_SECRET_KEY` 均**只拒绝注册**。生产 `TURNSTILE_SITE_KEY` 为公开配置，Secret 只在服务端环境；绝不把 test key 与生产 Secret 混用。`remoteip` 可省略，避免依赖 Streamlit 无可信来源保证的 IP 头。Turnstile token 有效 300 秒且单次使用，重放应失败；网络错误不得跳过验证。Siteverify 返回成功也不替代数据库注册限额。Cloudflare 的可选 `idempotency_key` 仅用于同一次验证请求的安全重试，不能当跨注册复用许可。[Siteverify 官方契约](https://developers.cloudflare.com/turnstile/get-started/server-side-validation/)。

CI/本地仅使用[Cloudflare 官方测试 sitekey/secret](https://developers.cloudflare.com/turnstile/troubleshooting/testing/)和可控 Siteverify stub。官方测试成功密钥会稳定通过，**不能单靠它证明真实 token 的 5 分钟失效与 single-use**；过期/重放由 stub 模拟 `timeout-or-duplicate` 并做服务层回归。CI 绝不请求生产 Turnstile 配置。

## B. Installation identity 与绑定

一方组件首次访问时用浏览器 CSPRNG 生成 32 字节随机 opaque `c2c_installation_id`，以 base64url 存在本站 localStorage。它与 `c2c_auth_session` 独立：不携带用户 ID、角色、Plan、密码或设备参数，不放查询参数，不与 auth token 互相推导。组件返回 `PENDING`/`PRESENT`/`UNAVAILABLE`；注册和平台 System AI 在没有有效 ID 时拒绝并给可理解的重试提示，登录、本地规则及已授权 BYOK 继续可用。不要用 sleep 假定异步读取完成。服务端校验格式后只计算 SHA-256 哈希；随机值有 256 位熵，哈希足够抵抗枚举，但**不能抵抗客户端自己更换 ID**。

选择“注册来源 + 当前 installation”双桶，而非仅按当前 installation，也不建立长期设备图谱：新用户注册时保存来源哈希；之后在另一设备登录不会锁号，System AI 预留同时检查当前设备桶与该用户注册来源桶。两个桶相同时只计一次。这样从 A 注册的多个 Free 账号即使登录 B，也仍共享 A 的当日池；B 上其他账号还会共享 B 的当日池。30 天后来源哈希不再参与识别，并在后续相关写事务中清除，届时只保留当前 installation 检查和每用户日额度；这是降低长期关联性的有意折中。旧生产用户来源为空，不强制重新注册；他们从新版本起按当前 installation 计费。无需 `user_installations` 关系表；后续若确需多设备关系，须单独证明收益并审查误伤。

这不是可信设备认证。无痕窗口、清 localStorage、复制或篡改 ID、不同浏览器/设备均可绕过或共享额度；同一校园 NAT 不因共用 IP 被视为同一 installation。共用电脑的学生可能共用 10 次池，需提供本地规则/BYOK 途径和客服审查，而非暴露内部计数。不得采集 canvas、字体、硬件、MAC、序列号或设备指纹 SaaS。

## C/D. 注册限额与 System AI 预留

注册先做用户名/密码本地校验，再做 Siteverify 与密码哈希计算，随后在**一个数据库事务**中按 `users.registration_installation_hash` 与 `users.created_time` 统计成功创建的账户：滚动 24h `<2` 且滚动 7d `<3` 才插入普通 `user + Free`。只有 `users` 提交成功才算成功注册；随后创建登录 session 若失败，用户仍可重新登录。用户名唯一冲突不计成功注册。失败尝试第一版只记不含标识的短期聚合指标，不创建逐次 `registration_events`；如以后确需调查，另定字段和不超过 7 天的保留期。达到限额显示“当前设备近期创建的账户较多，请稍后再试。”，不透露阈值、哈希或风控细节。不得以 IP 唯一限制注册。

`AIUsageService.start_call` 仅对 `key_mode=system` 增加 installation 检查。数据库在一次事务中先检查现有用户/Guest 日额度，再按东八区自然日检查当前 installation 桶、注册来源桶和全站预算，最后插入一条 `api_usage.status='reserved'`；任何一项失败均不插入，也不发出 Provider 请求。当前页面先调用 `provider_factory.create()` 再预留，DeepSeek 的模型目录解析在部分配置下可能访问外部；实施时应先用受控选择做本地验证，以选定模型 ID 预留，再创建客户端，创建失败则将预留标为失败。这样才能保证**任何外部 Provider 请求都发生在预留成功之后**。`reserved`、`success`、`failed` 都算当天已占用的一次，失败不自动返还，避免通过失败重试绕过成本控制。额度展示可提示“今日平台 AI 次数已用完”，不暴露具体 installation 计数。

Free 用户仍是 5/日，Free/Guest 共享 installation 10/日：同一来源的 A 用 5、B 用 5，C 当日为 0；Guest 的 2 次/匿名会话仍受该 10 次池约束。Pro/Developer 套餐使用独立 20/日池，Developer Mode 不抬高 Free 额度；Admin 可登录且不因公开注册风控受阻，但受绝对凭证熔断。`key_mode=user` 的 BYOK 仍只走原 BYOK 权限和用户 Key；本地规则不写 `api_usage`，两者都不扣公开补贴池。VERIFIED 模型目录、Provider 端点和密钥隔离不变。

## E/G. 最小 additive schema（预计 version 4）

| 现有表 | 计划增加 | 用途与保留 |
|---|---|---|
| `users` | `registration_installation_hash TEXT NULL` | 成功注册窗口及来源桶；旧用户为 NULL；来源关联满 30 天置 NULL，用户本身不删 |
| `api_usage` | `installation_hash TEXT NULL`, `quota_class TEXT NULL` | 新 System AI 预留的当前桶及当时额度类别；旧行/BYOK 可为 NULL；哈希满 8 天置 NULL，用量行保留 |

为上面两列增加最少的窗口查询索引；不建 `installations`、`registration_events` 或 `user_installations` 表。`users` 现有 `created_time` 足以统计成功注册，`auth_sessions` 继续只处理登录，不能拿认证 token 当 installation。`api_usage` 原有 `key_mode`、`status`、`user_id` 和时间足以核对个人额度与全站预算；`quota_class` 是历史套餐快照，避免 Plan 变更重写旧调用所属池。来源桶查询对 `api_usage` 左连 `users`：同一调用满足“当前 hash = 桶”或“其用户注册来源 hash = 桶”时**只计一条**。清理哈希后不再把旧数据纳入设备关联，但当日计数所需的 8 天数据尚在。注册/预留写事务限量幂等补清；不引入每日清理任务，也不承诺严格的 8/30 天物理删除时刻。审查索引与 `OR` 查询的实际 PostgreSQL 计划；小型作品集可先保持简单查询。

Migration 3→4 仅 ADD nullable 列与索引，并插入 schema 版本；SQLite/PostgreSQL 均在事务内执行，幂等重试、失败回滚。现有 users、auth_sessions、Key、报告和用量不删不改；不回填无法证明的旧 installation。应用启动不能自动把 test keys 写到生产。生产版本 3 二进制会拒绝高版本 schema，故**不能声称直接回滚旧 main 即可恢复**：上线前须备好识别 v4 且能关闭注册/系统补贴功能的兼容回退构建，或采取先兼容代码后 migration 的 expand/contract 顺序；不做降级 schema 或删除新数据。

## F. Email verification：DEFER_TO_E2

邮箱验证能增加人工批量开户步骤，却容易被一次性邮箱、邮箱别名和批量收件绕过，不能代替安装与全站额度。第一版增加邮件 Provider、发信 Secret、退信/送达监测、申诉与大陆网络可达性，还会收集新的个人信息；对公共求职作品集的展示收益低于可靠的 Turnstile + 原子化额度。在第一版暂缓，避免把邮箱误写成“一人一号”。**Turnstile + installation 10/日只能压低普通滥用，不能单独保证平台成本**；要先定并上线全站硬上限、单次模型调用上限和告警，才可认为补贴风险有预算边界。邮件是否进入 E2 取决于上线后的异常注册率、预算消耗和用户摩擦证据。

## H/I. 隐私与威胁模型

Installation ID 是防滥用的 pseudonymous identifier，不是现实身份或账户所有权证明。数据库仅保存其哈希，浏览器原值仅在本站 localStorage；不得记录密码、明文 auth/installation/Turnstile token、API Key、`DATABASE_URL`、加密主密钥或 Turnstile Secret。日志仅允许固定错误类别、计数区间与是否通过，不记录提交体、Siteverify 原始响应、异常原文或完整 IP。第一版不持久保存 IP；不信任客户端可伪造的转发头。Turnstile 是第三方挑战服务，**其自身会处理浏览器挑战信号**，隐私告知须说明这一点；本站不另建指纹或稳定个人画像。[Cloudflare Turnstile 概览与隐私说明入口](https://developers.cloudflare.com/turnstile/)。

| 威胁 | 处理与剩余限制 |
|---|---|
| 自动脚本、Turnstile token 重放 | 服务端 Siteverify + hostname/action + single-use；网络失败只停注册；人工打码仍可能通过 |
| 手动批量注册、同 installation 多账号 | 24h/7d 成功注册限额 + 来源桶 10/日；换新 ID/设备仍可绕过，靠全站预算封顶 |
| 无痕、清存储、换浏览器/设备、VPN/IP 轮换 | 当前桶可重置，来源桶对既有账号保留 30 天；不作一人一号承诺，不以 IP 硬封 |
| 校园 NAT、共享电脑、复制 installation ID | NAT 不关联；共享/复制 ID 共享额度，可能误伤，提供本地规则/BYOK，不泄露内部计数 |
| 并发注册/额度超支 | 计数与写入必须在同一事务串行化；见下节；不能先检查再另行插入 |
| BYOK 误扣、Admin 误伤 | 按 `key_mode` 明确分支；Admin 登录完全独立于 Turnstile，公开额度策略不覆盖管理员 |

### 原子性与锁顺序

沿用现有仓储的 `BEGIN IMMEDIATE`：SQLite 取得写锁；PostgreSQL `PostgresConnection` 将其映射到 transaction-scoped advisory lock。注册成功计数+用户插入、System AI 的用户/当前/来源/全站四重计数+`reserved` 插入均须各在一个事务完成。不要在持有锁时调用 Siteverify 或 Provider。现有全局 advisory lock 可先用于作品集流量，避免分别给用户/installation 加锁导致顺序不一致；若未来性能不足，再按固定字典序获取多把锁并补并发测试。所有写入路径必须共用该仓储边界，禁止另开“先读后写”捷径。SQLite/PostgreSQL 均测试两请求同时争最后一个名额时恰好一成功。

## J. 验证计划（实施阶段才运行）

- Turnstile：官方测试密钥与受控 stub 覆盖 valid、invalid、missing、expired/replayed、wrong hostname/action、网络超时、Secret 缺失；确保登录/本地规则/BYOK 不受 Siteverify 故障影响。
- 注册：第一、第二次成功；24h 第三次拒绝；7d 上限与窗口跨界；不同 installation；同名冲突不计成功；并发争最后名额；PostgreSQL/SQLite 一致。
- System AI：Free 5/日、Guest 2/匿名会话、来源与当前各 10/日、A5+B5+C0、跨设备登录、跨东八区午夜、并发预留、全站预算、失败也计数、Pro/Developer/Admin 已审定策略；BYOK 和本地规则不扣补贴池。
- 隐私：日志、数据库、URL 不出现明文 auth/installation/Turnstile token 或 Secret；8/30 天哈希清理后计数仍正确；旧用户 NULL 路径安全。
- 浏览器：新 installation→注册→reload→登录保持、同设备第二/第三账号、另一设备登录、平台额度、登出后刷新、390px、Cloudflare widget 在 Streamlit iframe 中的真实交互；只检查标识存在的布尔值，不输出值。

## K. 分阶段上线与回退

1. 离线实现：仅合成 SQLite 和 Cloudflare 官方测试密钥/stub；不接触生产 Turnstile/Provider。先定分池与全站预算数值。
2. CI：PostgreSQL 3.12/3.14 migration、并发、注册、额度、隐私回归；五个 job 全绿。
3. 本地真实浏览器：桌面/390px、注册失败和换设备路径，测试键与生产键隔离。
4. 生产配置：用户已人工创建限定 `mhj-course2career.streamlit.app` 的 Turnstile widget，并将 `TURNSTILE_SITE_KEY`、`TURNSTILE_SECRET_KEY` 保存到 Streamlit Secrets；本记录未读取或修改其值。v4 兼容回退构建仍可用，生产 widget 与注册流程已完成 smoke。
5. 生产 smoke：授权的一次真实注册和一次逻辑 System DeepSeek 提交已完成；System 只产生一条成功的 `api_usage` 预留，Guest、installation、公开全局及绝对桶各计一次。本地规则与登录持久化通过。Admin、已认证 Developer Mode、BYOK 的生产手工回归仍为非阻断的 `MANUAL_PENDING`，不写成已通过；详见[生产发布记录](c08-e1-production-release.md)。

若 Turnstile 或 installation 读取失败：只关闭**新注册**与受补贴 System AI，保留现有登录、本地规则、已授权 BYOK 和管理入口；不得在生产悄悄放行无挑战注册。若 v4 代码故障，回退到预备的 **v4-compatible** 构建，保持 additive schema 与既有数据，不恢复旧版 schema 3 二进制，也不删生产数据。功能开关若用于应急只能收紧补贴/关闭注册，不能绕开 Siteverify。重新开放前复核 CI 与生产 smoke。

## 后续运营观察

1. 真实生产 Turnstile widget、精确 hostname 与注册 smoke 已通过；继续观察目标访问网络中的挑战可用性和误伤，测试键不得进入生产配置。
2. 核对平台模型实际单次输出与供应商账单，设置必要告警；100/120 是调用数上限，不是精确货币预算。
3. 后续是否确有邮箱核验需求，待 E1 实际滥用与误伤数据再决定，当前不收集邮箱。
