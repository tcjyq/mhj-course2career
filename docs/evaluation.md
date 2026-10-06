# AI 输出评测方案

## PR #9 独立审查后的验证

首版 9.0 自评过于宽松，后续独立审查发现三个主要视觉问题；本轮不以提高分数作为停止依据。重新比较 reviewed head `9870c559214914ccd25bf690a8176327c2898403`，检查手机构图、报告艺术指导、视觉语言连续性、真实追溯交互和字级。全量 431 passed / 14 skipped（65.85s）；补充浏览器检查七宽度、21 个展开案例状态、维度真实原因、技能实际来源、跨案例回溯与键盘焦点、动态 reduced-motion。最后两轮完整截图审查与技术验证分别记录。[本轮报告](homepage-pr9-review-iteration.md)。

## 首页展示层首版验证（2026-10-06，未部署）

本轮不评测或调用真实 AI。全量本地测试为 **431 passed、14 skipped**；skip 保留现有条件，不伪称通过。新增回归核对公开合成 JSON 与当前规则，以及无 JS 默认报告的分数、完整度、置信度和独立门槛。七个指定宽度通过溢出和标题检查；展示交互、无 JS、读取失败与 reduced-motion 均检查实际浏览器。PR #7 的 7 组浏览器安全与导航回归通过，18 次普通导航均一轮。

首版视觉评分与技术结果分开，四轮浏览器截图中修复了移动字号、平板构图和截图等待策略；后续独立审查指出其评分过宽，当前结论见上方本轮报告。外部奖项标准作为参考，不表示获得奖项或评委认证。性能为本地浏览器冷加载与受限网络实验，不是生产 Core Web Vitals。[首版验收和原始数据](homepage-design-review.md)。

PR #8 review fix 增加 System/BYOK 冷/暖/过期/pinned/刷新失败与真实 generation 顺序的 Faux 回归、AccessMode 到 resolver/cache 传递、Developer 零 HTTP/零解密和 v0/v1 文案回归；全量、独立 PostgreSQL integration/restore、浏览器及 PR #7 结构指标重新验证，结果见候选报告的 review fix 记录。

## Provider 架构候选验证（2026-10-05）

先以两项失败测试复现“缺失/陌生 DeepSeek 返回模型仍 VERIFIED”，然后覆盖十家工厂路径、五条协议、实际 OpenAI SDK 离线 Schema 失败、fallback、缺失 usage、凭证隔离、Key 轮换、BYOK 禁用和 legacy 认证旁路。全部推理为 deterministic/Faux 或 MockTransport，REAL_AI_CALLS=0。具体全量测试、PostgreSQL 集成/恢复、独立审查修正及浏览器结果见[候选报告](provider-access-upgrade-20261005.md)。

与 main 526faf9 同环境各三次 warm run：Developer 8 SQL / 0 新物理连接 / 1 轮保持不变，Python median 153.04→154.53 ms；Analysis 7/0/1；quota、membership 4/0/1。没有自动 Provider HTTP。小样本耗时变化不是生产结论或显著性证明；没有宣称进一步提速。[原始样本](provider-access/20261005/benchmark-summary.json)。下面带日期的性能候选数值为此前阶段历史证据。

## 性能修复候选（2026-10-04，未部署）

本轮只测性能与权限回归，不产生模型请求。Python 3.12 全量 330 passed、1 skipped（restore DB 环境未设置）；独立 PostgreSQL 集成 13 passed，随后合成备份 / 恢复与恢复校验通过，补齐该跳过项。真实本地浏览器 7 组安全检查通过，普通 18 次导航均一轮；Ruff / 格式 / diff 门禁通过。

同 main 可比三次 warm run：Developer 58 → 8 SQL、58 → 0 新连接、2 → 1 轮，Python median 2382.98 → 148.95 ms；规则整页 1440.23 → 221.32 ms。空查询健康检查仍有成本，0 新连接只适用于 warm 动作。各阶段原始样本、身份隔离、revoke、Key version、pool 事务与生产未知边界见[专项实施报告](performance-fix-20261004.md)。`RELEASE_READY=no`，其它章节历史生产结果不代表本性能候选已部署。

## 发布后缺陷修复候选（2026-09-29）

当前生产 E1 smoke 的结论保持不变；A01—A08 的隔离修复及本地/CI 回归另见[修复报告](post-release-production-bug-fix-report-20260929.md)。候选分支测试不等于生产复测，不扩展 Provider 精确认证或已执行的人工回归范围。

## C08-E1 生产 smoke（2026-09-28）

PR #3 已合入 main，五项 CI 成功。生产 schema v4、真实 Turnstile widget 与注册、登录持久化、本地规则均通过。经页面的一次逻辑 System DeepSeek 提交成功提取 2 项技能；只读核对恰好一条新增 `api_usage`，状态 `success`、模型 `deepseek-flash`、`quota_class=public_free`，Guest/installation/公开全局/绝对桶均只增加 1。Provider 内部 HTTP 尝试次数及 fallback 使用情况未安全观测。生产测试账号密码曾泄露到任务工具日志，后续凭证哈希轮换、会话版本递增与全部未撤销会话清零，事件记为 `contained`，旧密码未重试。Admin、已认证 Developer Mode、BYOK 生产手工回归仍为非阻断 `MANUAL_PENDING`；证据与边界见[生产发布记录](c08-e1-production-release.md)。

## C08-E1 防滥用回归（合成环境）

SQLite 与 PostgreSQL CI 核对 schema v4 加法迁移、Turnstile 成功/失败/主机和 action/重放/网络失败、注册滚动 24 小时与 7 天、并发最后名额、Guest/Free/Pro/Developer Mode/BYOK 隔离、当前与来源 installation、全站 100 和绝对 120、东八区换日、哈希过期与清理。浏览器使用 Cloudflare 官方测试键和本地受控验证响应检查两次成功注册、第三次拒绝、登录刷新与 390px；该合成阶段未调用真实 Provider。测试键的固定成功不证明真实挑战的 300 秒失效或单次消费；这两项由受控 stub 测试。随后真实生产 widget 与注册 smoke 已单独通过，不能反推所有失败场景都做过生产破坏性测试。

当时本地 Python 3.12 全量 296 通过、0 跳过；隔离本机 PostgreSQL 18 的 4 项集成测试与备份恢复测试通过。浏览器测试键路径已覆盖两次成功注册、第三次拒绝、刷新保留登录与 390px 无横向溢出；这组本地证据本身不是生产 Turnstile 验收，也没有产生模型调用。生产验收另见上节。

## C08 持久登录回归

使用合成账号核对 SQLite/PostgreSQL 会话创建、哈希、过期、撤销、用户隔离、停用、密码轮换、管理员与开发者状态；特别模拟首次 `PENDING`、随后有 token 或明确无 token 的异步返回。真实本地浏览器核对 F5、Ctrl+R、新标签页、登出后刷新和 390px；用户另行确认生产环境 F5、Ctrl+R、新标签页及登出后 F5 均通过，`AUTH_SESSION_PERSISTENCE_READY=yes`。浏览器只检查本站 localStorage 是否有键，不输出 token 值；URL 不含 token。真实 Provider API 不参与此回归。

## 1. 评测目标

评测分为两部分：

1. JD 结构化提取效果，确认模型能稳定提取技能、重要程度和原文证据；
2. Career Adaptability Model v2.1 的确定性回归测试，确认硬门槛、技能迁移、五维评分和解释账本符合规则。

确定性评分不使用生成式模型评测，也不使用录用结果预测。

## 2. 人工审阅样例计划（尚未完成）

计划建立脱敏 JD 集合，至少覆盖数据分析、业务分析、产品、信息系统实施和开发岗位。每份样例由人工标注：规范技能、可接受别名、重要程度和证据句。

## 3. 指标

- 技能精确率：模型提取技能中人工认可的比例。
- 技能召回率：人工标注技能中被模型识别的比例。
- 重要程度准确率：已匹配技能的重要程度一致比例。
- 证据有效率：证据是否来自输入且支持判断。
- 契约通过率：响应能否通过 Pydantic 校验。

## 4. 测试方法

- 单元测试使用模拟响应，不产生 API 成本。
- C08-B1 十家预设均通过受控映射、fake SDK/transport、加密 Key、页面和仓储回归；这些测试不证明真实模型兼容性。每个拟投入生产的 Provider/模型组合还须用持有人自己的 Key 验证合成 JD → 提取 → `JobAnalysis`、实际模型回写、Token、错误脱敏及价格来源。费用未知必须保持 `unknown`，不能当作 0 元。
- C08-B2 固定 4 个合成 JD，逐个核对技能命中、否定项、`evidence_text` 原文、JobAnalysis、实际模型、usage 与脱敏错误；只有完整通过才是 `VERIFIED`。离线测试分别覆盖缺 Python、SQL、需求分析，误提 Java，非原文 evidence 和正确结果，并校验逐题诊断不写 JD、凭证或模型原始响应。2026-09-26 Bailian `cn-beijing` / `qwen3.8-flash` 和 DeepSeek `global` / `deepseek-flash` 均有 4/4 真实固定集、usage、返回模型匹配且错误为空的精确认证；之前百炼 1/4、OpenAI/Anthropic 401 仅属历史运行。业务断言失败不等于 JSON Schema 不兼容；离线 mock 测试也不证明其他模型真实可用。[真实证据与限制](c08-provider-validation.md)。
- C08-B3 权限回归覆盖普通 Free/Pro 自助开启后额度不变、游客拒绝、Admin 与历史 Developer Role/Plan、关闭后旧会话的 Key/Profile/用户 Key 调用拒绝、跨用户隔离、重开后密文不变，以及 SQLite 重复初始化和失败回滚。浏览器使用隔离假 Key 验证注册、登录、刷新、开关与 390px 布局；不发真实供应商请求。
- C08-C 离线测试需覆盖十家策略与大陆顺序、DeepSeek 旧名及价格合并、百炼分页/区域/Workspace、SiliconFlow chat 过滤、MiniMax 双端点、OpenRouter USD、未知价格、缓存 TTL/失败旧目录/跨用户与 Key 轮换、B3 关闭及重开、无效元数据和 401 脱敏。假响应通过不代表真实兼容；模型级 `VERIFIED` 仍以 B2 完整固定集为准。浏览器需复核注册 Free 用户开关、目录选择、国际折叠、390px 整体宽度及无真实凭证暴露。[目录与剩余证据](c08-model-discovery.md)。
- Prompt 或模型变更时，对固定黄金样例离线重跑并记录模型名、日期和指标。
- DeepSeek 白名单新增模型前，必须验证 JSON 契约、实际模型回写、Token usage、最大输出限制和 404 单次回退。
- 不要求生成文本逐字一致，只验证结构和语义标准。
- 发现误报时优先改进提示词或人工确认流程，不允许模型直接影响评分公式。
- 发布前使用真实浏览器验证侧边栏导航，首页切换到个人分析后不得残留首页流程区，控制台不得出现应用异常。

## 5. 岗位适配度回归测试

固定案例至少覆盖：

- 技能完全缺失时保留15分学习基础，不出现技能维度为零；
- 课程、项目、实习的直接证据；
- Python与Web后端向FastAPI等有限技能迁移；
- 项目和实习能够补偿部分技能不足；
- 学历、专业、毕业年份、到岗时间和城市硬门槛；
- 未填写信息使用中性值并降低资料完整度；
- 明确选择“目前没有项目/实习”产生可解释扣分；
- `50 + Σ加减分`与最终适配度一致；
- 学习路线最多8个能力模块；
- 代表性AI应用开发实习案例不过度依赖技能完全匹配。

评分权重、阈值、迁移规则或院校信号发生变化时，必须运行完整回归测试并在开发日志记录原因。

## 6. 公平性与边界检查

- 不把适配度表述为录用概率；
- 不因单项技能缺失直接判定“不适合”；
- 不把未填写信息按零分处理；
- 不把院校层次、学历或企业品牌解释为个人能力上限；
- 海外院校缺少可靠分层依据时使用中性值；
- 明确标注自评和潜力等主观输入未经独立核验，不把资料完整度当作可靠性；
- 页面必须同时展示硬门槛、维度分、证据和限制说明。

## 7. 历史报告回归验证

- 同一用户可保存并恢复 `AnalysisReport` 或 `AdaptabilityReport v2.1` 快照；
- 旧版快照必须进入旧版兼容视图，不得读取仅存在于 v2.1 的资格、五维或可信度字段；
- 两条时间、岗位和分数完全相同的记录必须仍可分别选择；
- 其他用户即使知道记录 ID 也不能读取该快照；
- 恢复操作不应回填原始课程、JD 或凭证。
- 保存或校验开发者 API Key 后，密码输入框和对应会话状态均应为空，密码组件标识必须更新，页面只允许显示末四位元数据。

## 8. 上线门槛

以下是尚未完成的人工评测目标，不是实测指标：契约通过率100%、证据有效率100%、技能精确率及召回率不低于85%。本次固定响应回归与合成演示不能替代这些评测，默认体验使用本地规则。

GitHub 模型监测发现的新模型不视为通过评测。只有完成上述固定样例与供应商契约测试，并更新白名单和优先级后，Auto-Safe 才能选择该模型。

模型调用回归还必须覆盖 Streamlit 热更新窗口：供应商结果只生成一次；缓存旧仓储不接受实际模型字段时，状态、Token 和费用仍应成功回写，且不得自动重试付费请求。

## 9. 公开招聘展示验收

- `course2career.tcjyq.cc` 必须返回静态 Showcase，匿名访问不出现登录、数据库、Secrets 或 API Key 错误；
- Showcase 的“在线体验”必须精确指向 `https://mhj-course2career.streamlit.app`，“GitHub”必须精确指向 `https://github.com/tcjyq/mhj-course2career`；
- Streamlit Demo 在没有平台 AI Key 时只提供本地规则，并能由游客走完上传课程、输入 JD、确认技能和生成报告的核心流程；
- 截图必须逐字节对应仓库已有 `screenshots/home.png`，不能以生成图代替；
- 用桌面与窄屏浏览器检查首屏、导航、外链、焦点样式和截图可读性。Community Cloud 的休眠属于平台行为，只验证首次访问可按平台机制正常唤醒，不实施保活或定时 ping。

## 2026-09-21 本地优化验证

本次自动测试证据、命令及环境限制统一见 [优化交付记录](optimization-review.md)。合成案例和固定响应测试只是代码／契约回归，不能称为人工gold或独立评测集。真实目标用户任务测试、正式人工标注与新角色模板仍为P2，尚未实施。

## C08-D0 发布评估

SQLite 单元回归与 PostgreSQL 服务容器集成分别记录；前者通过不推断后者可用。独立集成覆盖新库、重新连接、用户及 BYOK 资产、用量/额度、跨用户隔离和合成 SQLite 迁移。真实大陆 Provider 必须在持久化基础上使用 B2 合成固定集取得 exact model、usage、返回模型和证据定位；仅 `/v1/models` 或连接测试成功不计 VERIFIED。D1 所需 PostgreSQL CI、独立远程合成演练、备份恢复与两款精确模型验证已有证据；D2 合成完整路径与桌面/390px 浏览器证据见[候选报告](c08-d2-release-candidate.md)。合成 Provider 不等于真实模型重测；生产 Secrets 已由用户人工确认保存，但生产运行时尚未验收，`RELEASE_READY=no`。
