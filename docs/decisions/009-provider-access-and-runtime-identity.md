# ADR 009：增量 Provider 访问语义与运行时模型身份证据

日期：2026-10-05。状态：候选，待 Draft PR 审阅。补充 ADR 003/004/006，不替代历史决策。

## 背景

旧适配器将请求模型用作缺失/陌生返回模型的usage标签，验证器由usage.model判断精确身份，可能误认证。品牌、协议、credential所有权与认证类型也未明确分层。PR #7已降低render数据库成本，本轮不能重建全套SDK或恢复隐式联网。

## 决定

保留ProviderPreset、APIKeyService、原协议adapter与JobAnalysis接口；增加只开放API的AccessDefinition、独立CredentialKind/Resolver、小型显式兼容声明。user/system仍是所有权；不引入OAuth数据库或未获安全验证的订阅流程。所有官方端点由原声明控制，不用URL猜compat或接受SDK ambient base URL。

ModelTrace/ModelAttempt不可变且只存模型ID、安全错误码与fallback原因；每次call reset。真实返回不得以请求/usage标签替代。统一last_result包含JobAnalysis、usage、trace、provider/endpoint与证据；原extract_job_skills返回值兼容。新认证默认v1，逐次原始身份证据完整匹配才VERIFIED；仅loader接受无版本旧记录为legacy，新增legacy VERIFIED拒绝。历史认证不删除、不重新声称raw证明。

目录读取/默认解析只用最后已知缓存；2026-10-05 review fix 恢复显式 AI auto_safe 冷/过期缓存最多一次 refresh，成功后使用原 approved/preference primary/fallback。warm/pinned 不刷新，失败保留原 stale 安全窗口或配置模型，单404 fallback不变。SDK自动retry统一0，预算1或既有fallback2；本轮不建通用重试/流式事件框架。

## 来源与取舍

参考Pi AI在200387122ca450d6387f033949423114a270b96c的Provider ownership、typed auth、explicit catalog、compat与faux思想；自写Python适配，不复制实现/添加依赖。Pi provider-only凭证存储、URL guessing和本地OAuth/CLI runtime不适用于C2C直接照搬。Copilot官方多用户服务器许可明确，但完整安全OAuth/runtime与JobAnalysis证明超出小PR，模式继续关闭；其他套餐不能从Pi支持反推许可。

## 后果与验证

不改DB schema、默认模型、价格、quota、权限或评分。账目标签仍兼容，raw身份独立；未知/别名返回可能只Schema-compatible，是保守认证而非拒绝合法分析。新增加的状态文案和测试有轻微render成本，同环境3次warm保持SQL/连接/普通导航指标，耗时变化记录且不称显著提速。真实认证、订阅OAuth与生产验收需独立授权；本轮REVIEW_PR。

[实施、测试及限制](../provider-access-upgrade-20261005.md)。
