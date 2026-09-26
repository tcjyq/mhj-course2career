# ADR 003：按 API 协议组织官方 Provider 预设与用户 BYOK

日期：2026-09-23。状态：C08-B1 本地实施，生产未发布。

## 背景

C08-A 只有四家基础预设，其中百炼/OpenRouter 尚无页面配置；逐家复制完整 Provider 类会使认证、区域、模型和页面逻辑分散。十家 Tier 1 Provider 的 API 格式可以归到 OpenAI Responses、OpenAI Chat Completions、Anthropic Messages 与 Gemini Native 四类。已有 OpenAI Responses 与 DeepSeek Auto-Safe 路径需保持稳定。

## 决定

使用不可变 `ProviderPreset` 保存官方端点 ID、协议和能力策略；工厂按协议建立适配器，并保留 OpenAI/DeepSeek 已验证过的专用行为。六家 OpenAI Chat 兼容 Provider 共用适配器；MiniMax 的 `reasoning_split` 为小型 capability adapter。Anthropic 与 Gemini 使用各自原生 REST 请求。模型级验证状态不由预设推断。

`ProviderProfile` 只保存当前用户的端点 ID 与模型 ID，Key 仍由原 `APIKeyService` 使用 AES-256-GCM 加密。服务层按角色和套餐授权；`key_mode=user` 不占平台系统额度。SQLite 以事务把旧 2/4 Provider `CHECK` 扩到十个稳定小写 ID，原样保存密文、nonce、时间戳及 `course2career:{user_id}:{provider.value}` 关联数据。新调用费用状态区分 `estimated` 与 `unknown`。

## 结果与限制

新增兼容供应商通常只需官方预设及必要的小型适配，分析服务不依赖具体供应商。静态端点可限制 Key 的目标域名，禁止用户自填 URL。官方端点及认证依据见 [C08 官方矩阵](../c08-provider-matrix.md)。配置卡片和 fake 协议测试不等于真实模型验证；C08-B2 再逐模型验证，C08-C 才做通用目录与价格元数据，C08-D 才评估自定义端点和 SSRF 防护。生产迁移前须完成备份恢复演练。
