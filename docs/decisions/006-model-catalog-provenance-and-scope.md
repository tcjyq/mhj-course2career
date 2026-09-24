# ADR 006：官方模型目录与真实验证分层

日期：2026-09-24。状态：已采纳于 C08-C 本地实现，未发布。

## 决策

`ProviderPreset` 仅声明受控端点、协议与发现策略；`ModelCatalogService` 通过官方 API 或注明日期的短静态目录生成 `ModelCapability`。可用性、能力、价格分别记录来源；B2 的 `VerificationRecord` 按 Provider × endpoint × exact model 合并，不从官方能力或预设推断 `VERIFIED`。价格未知用 `None`，币种不换算。DeepSeek 旧模型名保留兼容标签，由用户主动迁移 Profile。

动态目录缓存按用户、Provider、端点、Workspace 和 Key 版本隔离，TTL 后可刷新，失败时保留旧目录并标过期。每次读取缓存或发现模型前复核 B3 开关。仅官方受控端点可请求，禁止重定向；Key 仅运行时解密，不写入模型元数据。C08-D 的自定义端点另行设计 SSRF 防护。

## 理由与后果

账号权限、区域和上游目录会变化，静态全局模型列表容易误导用户。官方 JSON 支持也不能证明 `JobAnalysis` 完整提取契约；将两层证据分开能避免错误升级验证状态。代价是无 Key、无来源或未验证模型会显示未知并需用户核对；内存缓存跨进程不会保留，Kimi/GLM 静态快照需要定期人工更新。生产发布仍须真实 B2 验证和安全评审。
