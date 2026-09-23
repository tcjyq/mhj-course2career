# Open Source Research — C08-OSS

研究日期：2026-09-23（东八区）。范围是 C08-B 前的架构与许可证研究；没有向第三方发出真实 API Key、调用真实模型、复制第三方代码、安装依赖或修改生产环境。本文的 Stars、端点和模型能力是日期快照，实施前须复核。

## Projects reviewed

用 GitHub 搜索了 `multi provider llm`、`byok llm provider`、`openai compatible provider registry`、`openai anthropic gemini adapter`，并定向检查下表四个成熟项目。搜索还出现 [mnfst/llm-gateway](https://github.com/mnfst/llm-gateway)、[ageerle/ruoyi-ai](https://github.com/ageerle/ruoyi-ai) 等；本轮没有完成其许可证及代码审计，故不作为复用依据。

Stars 和最后推送时间取自 2026-09-23 的 GitHub [仓库 API](https://docs.github.com/en/rest/repos/repos#get-a-repository)，均为随时变化的参考值；活跃不等于适合引入。下表的「复用级别」是 **Course2Career 技术与产品建议**，不是单纯的法律许可结论。

| Project | Stars / Activity（快照） | License | Relevant feature | Reuse level | Why |
| --- | --- | --- | --- | --- | --- |
| [CC Switch](https://github.com/farion1231/cc-switch) | 约 134.8k；2026-09-23 仍推送 | [MIT](https://github.com/farion1231/cc-switch/blob/main/LICENSE) | 预设目录、用户 Provider 配置、协议标签、切换及导入导出 | B | 预设与配置分离很有用；桌面应用的任意端点与本地配置不适用于多用户服务端。 |
| [LibreChat](https://github.com/danny-avila/LibreChat) | 约 44.7k；2026-09-23 仍推送 | [MIT](https://github.com/danny-avila/LibreChat/blob/main/LICENSE) | `user_provided` Key、加密存储、模型获取、原生 Anthropic 路由 | B | 端到端 BYOK 安全经验可借鉴；Node/Mongo 实现不适合照搬进小型 Streamlit 应用。 |
| [LiteLLM](https://github.com/BerriAI/litellm) | 约 59.4k；2026-09-23 仍推送 | [核心 MIT；enterprise 另有许可证](https://github.com/BerriAI/litellm/blob/main/LICENSE) | Provider 解析、能力映射、价格目录、用量归一化 | B | 适合借鉴分层；全量依赖、代理/路由/计费表面远超本项目需要；`enterprise/` 不在 MIT 范围。 |
| [Open WebUI](https://github.com/open-webui/open-webui) | 约 152.9k；2026-09-22/23 仍推送 | [现行 Open WebUI License](https://github.com/open-webui/open-webui/blob/main/LICENSE) | Connections、管理员配置、模型列表和用户视图 | C（Reference Only） | 现行许可包含品牌限制；只观察交互与信息架构，不复制现行代码或界面。 |

### License gate

| Repository / relevant component | Can copy code? | Can adapt? | Attribution required? | Recommended usage |
| --- | --- | --- | --- | --- |
| CC Switch；[preset 数据形状](https://github.com/farion1231/cc-switch/blob/main/src/config/claudeProviderPresets.ts)、[Provider 配置](https://github.com/farion1231/cc-switch/blob/main/src/types.ts)；MIT，Copyright (c) 2025 Jason Young | 许可证允许保留 MIT notice 的局部复制；本轮未复制 | 是，保留版权与许可文本 | 复制/改编表达性代码时需要 | B：独立设计 Python schema，手工核实官方端点；仅在确有收益时对小型片段做 A 级移植。 |
| LibreChat；[Key 存取](https://github.com/danny-avila/LibreChat/blob/main/packages/data-schemas/src/methods/key.ts)、[custom 初始化](https://github.com/danny-avila/LibreChat/blob/main/packages/api/src/endpoints/custom/initialize.ts)；MIT，Copyright (c) 2026 LibreChat | 许可证允许保留 MIT notice 的局部复制；本轮未复制 | 是，保留版权与许可文本 | 复制/改编表达性代码时需要 | B：复用流程和测试场景，不移植 TypeScript/Mongo 代码。 |
| LiteLLM；[Provider 解析](https://github.com/BerriAI/litellm/blob/main/litellm/litellm_core_utils/get_llm_provider_logic.py)、[模型成本目录](https://github.com/BerriAI/litellm/blob/main/litellm/litellm_core_utils/get_model_cost_map.py)；核心 MIT，Copyright (c) 2023 Berri AI；`enterprise/` 另行授权 | **仅 MIT 范围**理论上可，当前不建议复制；`enterprise/` 不按 MIT 处理 | 核心 MIT 可改编，仍需 notice | 复制/改编时需要，须逐文件确认路径与许可 | B：学习能力分层与来源标记；不把全量目录当已验证事实。 |
| Open WebUI；[Connections 后端](https://github.com/open-webui/open-webui/blob/main/backend/open_webui/routers/openai.py)；现行 Open WebUI License | 当前项目策略：不复制现行代码/UI | 当前项目策略：不改编现行表达性代码/UI | 若以后另议，先做逐文件和版本许可审查 | C：只参考管理员/用户分离、模型列表体验。 |

分级含义：A 为有独立小片段可在许可和 notice 完整时局部复用；B 为借鉴或重写设计；C 为参考；D 为不得使用。本轮 **没有实际 A 级代码移植**，也没有把任何无 LICENSE、GPL/AGPL 或 Open WebUI 现行代码带入仓库。[Open WebUI 的 LICENSE_HISTORY](https://github.com/open-webui/open-webui/blob/main/LICENSE_HISTORY) 给出旧版边界：`a76068d69cd59568b920dfab85dc573dbbb8f131` 之前为 MIT，至 `60d84a3aae9802339705826e9095e272e3c83623` 之前为 BSD-3；旧版若要使用，须锁定具体 commit 与文件逐项审查，不能用旧许可证覆盖现行代码。

## Architecture comparison

| 维度 | CC Switch | LibreChat | LiteLLM | Open WebUI | Course2Career 当前 / 建议 |
| --- | --- | --- | --- | --- | --- |
| Provider preset | 大型静态预设、模板变量、候选端点与 `apiFormat` | 管理员 custom endpoint 配置和内置端点 | Provider/模型映射及配置 | Connections 配置 | 已有 4 个受控预设；C08-B 扩至 10 个精简官方预设。 |
| Custom provider | 本地自定义 URL/配置 | 管理员可配置；可设用户提供 URL | 动态 `api_base` 与多种代理 | 可配置连接 URL | C08-D 才开放，C08-B/C 只使用官方受控端点。 |
| Protocol abstraction | `anthropic`、`openai_chat`、`openai_responses`、`gemini_native`（其 Claude Code 代理语境） | 默认 OpenAI compatible；`provider: anthropic` 改走原生 Messages | 大量 Provider 适配器和请求/响应转换 | 以 OpenAI compatible 连接为主，另有 Anthropic 分支 | 四种 API 协议作为执行适配器；ProviderPreset 选择协议及小型例外策略。 |
| API key storage | 本地桌面配置，安全假设不同 | 用户 Key 按用户/endpoint 加密存取；管理员 secret 单独处理 | 代理密钥管理与环境/路由配置 | 管理员/用户连接分层；本轮未确认所有存储路径的加密保证 | 保留现有 `APIKeyService`、AES-256-GCM 及用户/Provider 关联数据。 |
| Model discovery | 有 `modelsUrl` 或候选路径 | `models.default`/`fetch`，按 URL、Key、headers、用户隔离缓存 | 模型目录与动态 Provider 解析 | 对连接获取 `/models`，整理管理员/用户视图 | C08-C 加 `/v1/models` 等策略、缓存和失败回退；B 仅手工确认模型。 |
| Capability detection | 部分模型目录/推理参数配置 | 端点参数和模型配置 | 按模型+Provider 求支持参数 | 连接配置/模型元数据 | C08-C 用模型级 verified/unverified 及来源；B 仅已验证能力入请求。 |
| Pricing | 用量配置，非本项目价目来源 | token config 可由管理员指定/获取 | 大规模 `model_cost` 目录和成本计算 | 模型配置/用量展示 | 保留估算成本；未知价格为 unknown，不以 0 冒充免费。 |
| Usage | 桌面用量功能 | 端点 token config / 用户消费 | 统一 token/cost 包装 | 请求/模型使用 | 保留当前 `AIUsageService` 的实际用量与成本估算。 |
| Security | 本地桌面信任边界 | 用户 URL 验证、allowlist、用户缓存隔离、用户 URL 禁转管理员 header | 主机/路径精确匹配，防止把服务端 Key 发往攻击者 URL | 管理员/用户权限区分；不能据此推断任意 URL 安全 | B/C 端点由代码固定；D 必须独立 SSRF/重定向/DNS/凭证域威胁评审。 |
| Server-side SSRF concern | 本地端点功能不能直接移植 | 显式检查用户提供 URL | 动态 URL/凭证路由需严格匹配 | 可配连接是服务器出站面 | 当前无任意 URL；C08-D 在服务端有高风险。 |

依据：[CC Switch preset](https://github.com/farion1231/cc-switch/blob/main/src/config/claudeProviderPresets.ts)、[本地 endpoint CRUD](https://github.com/farion1231/cc-switch/blob/main/src-tauri/src/services/provider/endpoints.rs)、[导入导出](https://github.com/farion1231/cc-switch/blob/main/src-tauri/src/commands/import_export.rs)；[LibreChat Key 方法](https://github.com/danny-avila/LibreChat/blob/main/packages/data-schemas/src/methods/key.ts)、[初始化](https://github.com/danny-avila/LibreChat/blob/main/packages/api/src/endpoints/custom/initialize.ts)、[模型配置](https://github.com/danny-avila/LibreChat/blob/main/packages/api/src/endpoints/config/models.ts)、[官方 custom endpoint 文档](https://www.librechat.ai/docs/configuration/librechat_yaml/object_structure/custom_endpoint)；[LiteLLM Provider 解析](https://github.com/BerriAI/litellm/blob/main/litellm/litellm_core_utils/get_llm_provider_logic.py)、[参数能力](https://github.com/BerriAI/litellm/blob/main/litellm/litellm_core_utils/get_supported_openai_params.py)、[价格计算](https://github.com/BerriAI/litellm/blob/main/litellm/cost_calculator.py)；[Open WebUI Connections](https://github.com/open-webui/open-webui/blob/main/backend/open_webui/routers/openai.py)。

### 值得保留的具体机制

- **CC Switch**：`ProviderPreset` 和持久化 `Provider`/profile 分离；预设承载显示名、Key 获取入口、协议、端点候选和模型列表策略。其 [用户手册](https://github.com/farion1231/cc-switch/blob/main/docs/user-manual/en/2-providers/2.1-add.md) 展示选择预设后填写 Key/配置的流程。Course2Career 只吸收数据化思想，不能照搬桌面端任意 URL、SQL 导出或应用配置文件切换。
- **LibreChat**：`apiKey: user_provided` 的生命周期是用户界面输入 → 按 `userId + endpoint` 加密存储 → 选择 endpoint 时解密取出 → 选择/获取模型 → 用对应 Key 发请求；删除与过期也是独立操作。custom endpoint 默认 OpenAI compatible，显式 `provider: anthropic` 才使用原生 `/v1/messages`；原生 Anthropic 需显式 `models.default`，不能假设 OpenAI `/models`。用户提供 URL 时会验证端点，且不会向该目的地传送管理员 header 模板；模型缓存隔离 URL、Key、header 和用户。来源见[官方配置](https://www.librechat.ai/docs/configuration/librechat_yaml/object_structure/custom_endpoint)、[Key 方法](https://github.com/danny-avila/LibreChat/blob/main/packages/data-schemas/src/methods/key.ts)、[运行时初始化](https://github.com/danny-avila/LibreChat/blob/main/packages/api/src/endpoints/custom/initialize.ts)和[模型加载](https://github.com/danny-avila/LibreChat/blob/main/packages/api/src/endpoints/config/models.ts)。
- **LiteLLM**：把 Provider 识别、参数能力、请求转换、响应/Token 归一化和价格数据分开。其[端点匹配逻辑](https://github.com/BerriAI/litellm/blob/main/litellm/litellm_core_utils/get_llm_provider_logic.py) 特别说明子串匹配可能导致服务端 Key 发往攻击者域名；这是 C08-D 安全测试素材。其[基础依赖](https://github.com/BerriAI/litellm/blob/main/pyproject.toml)已经包括 HTTP、tokenizer、Pydantic 等，而整个项目还有大量可选代理/企业功能。本项目仅有 10 个目标预设、4 类协议，直接依赖会扩大升级、配置及安全维护面，当前不建议引入。
- **Open WebUI**：管理员连接配置与普通用户模型视图、模型获取路径可观察；[后端路由](https://github.com/open-webui/open-webui/blob/main/backend/open_webui/routers/openai.py) 区分管理员配置路由与普通用户模型路由。仅用于产品体验参考，不复制现行 Svelte/Python 代码、图标、品牌元素或界面表达。

## Provider Preset 推荐最终结构

静态 `ProviderPreset` 与用户的 `ProviderProfile` 分开。建议结构如下（**伪结构，非已实现接口**）：

```text
ProviderPreset:
  provider_id, display_name, primary_protocol
  official_endpoint_by_region, allowed_endpoint_ids
  api_key_help_url, auth_scheme, key_setting_policy
  default_model_or_none, model_discovery_strategy
  structured_output_strategy, reasoning_strategy, usage_strategy
  capability_adapter_id, pricing_source_policy, status

ProviderProfile (per user):
  user_id, provider_id, selected_endpoint_id, selected_model_id
  encrypted_key_reference, created_at, updated_at

ModelCapability (per provider + endpoint + model):
  model_id, structured_output, reasoning, context_window
  input_price, output_price, currency, unit, source_url, checked_at
  verification: verified | unverified | unsupported | unknown
```

`official_endpoint_by_region` 只存代码受控 URL，UI 只传端点 ID；Key 仍在现有 `APIKeyService`，不把密文或明文放进 preset/profile 序列化。`default_model_or_none` 允许尚未核实的 Provider 暂无默认模型。Provider 级能力只是初值；真实 JSON/推理能力应以 **Provider × 协议 × 模型 × 区域** 为准。模型列表存在不等于模型能满足 `JobAnalysis` 结构化输出。`verified` 必须有官方文档与本项目受控验证记录；没有真实验证就标记 `unverified`。价格带币种、单位、来源、检查时间，未知值保留空值。这样以后增加兼容供应商主要是新增 preset，只有协议差异才加小型 capability adapter。

| Tier 1 Provider | C08-B 首选协议 | 端点/模型原则与来源 |
| --- | --- | --- |
| OpenAI | OpenAI Responses | 沿用已发布 Responses 路径；按当前受控配置。 |
| DeepSeek | OpenAI Chat Completions | 沿用已发布 Auto-Safe、安全模型选择与官方受控端点。 |
| Alibaba Model Studio / Bailian | OpenAI Chat Completions | 沿用 C08-A [官方区域端点](https://help.aliyun.com/en/model-studio/base-url)白名单；区域与 Key 一致。 |
| OpenRouter | OpenAI Chat Completions | 沿用 [官方 API 根路径](https://openrouter.ai/docs/quickstart)；模型须明确指定，未知模型不自动开放。 |
| SiliconFlow | OpenAI Chat Completions | [官方 quickstart](https://docs.siliconflow.cn/docs/userguide/quickstart)使用 `https://api.siliconflow.cn/v1`；模型能力逐项验证。 |
| Moonshot / Kimi | OpenAI Chat Completions | [官方 Chat API](https://platform.kimi.com/docs/api/chat)；中国/国际平台的 Key 与端点组合须在 B 中按官方区域文档核实。 |
| Zhipu / GLM | OpenAI Chat Completions | [官方 HTTP 文档](https://docs.bigmodel.cn/cn/guide/develop/http/introduction)；中国/国际平台域名和区域 Key 分别核实。 |
| MiniMax | OpenAI Chat Completions | [官方 OpenAI SDK 文档](https://platform.minimax.io/docs/api-reference/text-openai-api)使用 `https://api.minimax.io/v1`；推理字段有模型差异，需小型 adapter。 |
| Google Gemini | Gemini API | [官方 `generateContent` API](https://ai.google.dev/api/generate-content)；使用原生认证、请求/响应及 usage 映射。 |
| Anthropic Claude | Anthropic Messages | [官方 Messages API](https://platform.claude.com/docs/en/api/messages/create)；使用原生协议，不伪装成 Chat Completions。 |

Tier 2：ModelScope、StepFun、xAI 和其他主流 Provider，仅在官方端点、Key 归属、模型能力与维护成本核实后追加预设。以上是 **目标接入矩阵**，不表示 C08-A 已支持十家，也不表示本轮完成真实供应商调用。

## Recommended reuse

**可直接使用**：现有 Course2Career 的 `LLMProvider`、`ProviderFactory`、`ProviderRegistry`、`APIKeyService`、AES-256-GCM、用量记录和系统/用户额度隔离；第三方**没有**实际移植的代码。许可上 CC Switch/LibreChat/LiteLLM 核心的 MIT 小片段可在逐文件确认和保留 notice 后考虑，但当前重写结构比跨语言复制更简单。

**只改写思想**：CC Switch 的 preset/profile 分离和协议标签；LibreChat 的 `user_provided` 生命周期、模型缓存作用域、原生 Anthropic 分流；LiteLLM 的模型级能力/价格来源和 Token 归一化；Open WebUI 的管理员/用户连接信息层次。保留现有 DeepSeek、OpenAI 专用逻辑，新增共享协议适配器及必要的小型 capability adapter。

**不使用**：CC Switch 的任意本地端点和 SQL 导出作为服务端安全模式；LibreChat 的整套 Node/Mongo 配置与任意用户 URL；LiteLLM 的全量依赖或未审计价格表；LiteLLM `enterprise/`；Open WebUI 现行代码/UI/品牌；未知许可证或未核实的 50+ preset 数据。C08-B 不开放任意 Custom Base URL。

## Attribution requirements

本轮只阅读和独立撰写分析，**无第三方代码、数据表或 UI 资产复制**，无需新增 `THIRD_PARTY_NOTICES.md`。文中链接标明设计来源。以后若实际移植，先建立 notices 并逐项记录 `source repo`、固定 commit、`source file`、license、原始 copyright、`modified files`、修改摘要及应保留的 notice；将许可文本随分发保留，不能把第三方贡献说成独立原创。特别排除 LiteLLM `enterprise/`；Open WebUI 历史版须先锁定旧 commit 与对应许可证边界。

## C08-B / C / D 边界与验证

- **C08-B — Mainstream Provider Presets + Developer BYOK**：十家 Tier 1 Provider 的受控官方 preset、Developer/Admin Key 生命周期和协议适配；不为每家复制一整个 Provider 类。免费用户系统 AI 仍固定 DeepSeek；BYOK 不扣平台 system quota；所有用户 Key 加密。新增 Provider 只接受官方端点 ID，不接受任意 Base URL。每家至少覆盖 UI 可选性、Key 隔离、受控端点、请求协议、结构化输出/验证失败、Token/费用未知状态、错误脱敏和 fake SDK 回归；真实兼容性须另有沙盒证据，不能凭 fake 测试宣称。
- **C08-C — Model Discovery**：按协议/供应商选择 `/v1/models` 或官方目录 API；缓存与失效、用户/端点作用域；模型能力 `verified/unverified`、价格/上下文元数据及来源时间；未知能力不自动提升为 verified。
- **C08-D — Custom Provider**：用户选择协议与自定义端点，做端点探测和连接测试；在发出凭证前完成 SSRF 防护（解析后的 scheme/host/port、DNS/IP 及重绑定、重定向、代理和内部地址限制）、凭证域隔离与审计。C08-D 不等于自动发布，生产发布另设评审门槛。

### Recommended implementation plan for C08-B

1. 在现有 `ProviderRegistry` 上拆清静态 preset、用户 Key/profile 与模型级能力；新增受控的四类协议标识。保持现有 OpenAI Responses 和 DeepSeek Auto-Safe 的公开行为及旧 ID 不变。所有 Key 写入现有加密服务；部署系统 Key 继续由受控环境 Secret 管理，不写入 UI/日志/明文数据库。
2. 先扩展十个稳定 Provider ID 与 Key 存储约束，设计可重复迁移及回滚；原有 `user_api_keys` 密文、nonce、AES-GCM 关联数据原样保留。不要通过更换 Provider 字符串导致旧 Key 无法解密。
3. 将现有兼容 Chat 适配器用于百炼、OpenRouter、SiliconFlow、Moonshot、Zhipu、MiniMax；MiniMax 等仅在有测试证据时加小型请求/响应能力适配。Anthropic Messages 与 Gemini API 分别增加共享协议适配器；不要按供应商复制完整类。OpenAI/DeepSeek 原路径继续使用。
4. 为每个 preset 人工核对官方域名、区域、认证格式和候选模型；持久化端点 ID 而非用户传入 URL。供应商和模型验证状态分开：页面只开放已通过当前项目结构化 `JobAnalysis`、错误处理及 Token 用量验证的组合。价格未知时显示「未配置估算」。
5. Developer/Admin 页面由 registry 生成 Provider 与 Key 设置，不向免费用户开放 BYOK 选择；`key_mode=user` 的额度隔离在服务层复验。覆盖跨用户/跨 Provider Key 隔离、密文升级、协议路由、官方域名固定、JSON 失败、用量与成本未知、日志脱敏的回归测试。
6. 用 fake SDK 完成可重复回归，再在独立沙盒逐 Provider/模型验证真实协议与结构化输出，标明未测组合。完成相应 README、需求、架构、UI、用户指南、评估、日志与示例同步后，单独进行发布评审；C08-C/D 不在本轮实施。

本轮验证：GitHub 文件/许可证与官方文档人工核查；本地仅文档变更，未运行模型调用、浏览器验收或供应商连接测试。代码测试与格式检查结果在本轮交付时另行记录。

## 后续落实：C08-B1

以上“本轮”指独立提交的 C08-OSS 研究阶段。后续 C08-B1 已按该研究独立实现十家官方预设、四类协议路由、用户 Key/Profile 隔离及 fake 回归；没有移植第三方代码或资产。C08-B2 已进行两次真实连接，均因 401 停止，没有模型通过固定验证集；[官方 Provider 矩阵](c08-provider-matrix.md)与 [B2 验证报告](c08-provider-validation.md)记录当前证据。历史研究中的“建议实施计划”保留为研究结论，不代表全部后续验证已完成。
