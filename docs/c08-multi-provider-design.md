# C08 多供应商设计与阶段状态

状态：C08-A 为历史基础；C08-B1 已在本地分支实现十家官方预设的 Developer/Admin BYOK 配置与协议适配，未发布，真实供应商调用待验证。官方端点证据见 [C08-B1 矩阵](c08-provider-matrix.md)。

## 起点与现状审计

起始生产 `main`：`3c9378683640bfbeb1ddcaec1a909a8ca0286c82`。

| 位置 | 当前契约与问题 |
|---|---|
| `llm_provider.py` | `ProviderName` 的旧序列化值为 `openai`、`deepseek`；`LLMProvider` 约定供应商、模型、最后一次 Token 用量和技能提取。新增枚举值不能改旧值。 |
| `llm_client.py` | OpenAI 使用 Responses API 的 Pydantic 结构化解析；继续保留。 |
| `llm_providers.py`、`model_catalog.py` | DeepSeek 使用 Chat Completions JSON 模式、禁用 thinking、Auto-Safe 白名单、目录缓存和 404 单次回退；继续保留。 |
| `provider_factory.py` | 原先按供应商分支创建客户端，并按供应商分支读取系统 Key；现在先解析受控预设，新供应商走共享兼容适配器。 |
| `api_key_service.py`、`key_encryption.py` | 用户 Key 由角色和套餐双重授权；AES-256-GCM 关联数据为 `course2career:{user_id}:{provider.value}`。旧值和密文不变。 |
| `product_repository.py` | `user_api_keys.provider` 原有 SQLite `CHECK` 仅允许两值；启动时以事务扩展为四值，原样复制密文、nonce 和元数据。`api_usage.provider` 本来是文本。 |
| `ui/analysis_page.py`、`ui/developer_page.py` | 原有字符串标签、供应商选择和费用取值散落在页面；改从预设取标签、已开放页面选项和配置费率。 |
| `access_services.py` | `key_mode=user` 不消耗系统日额度；用量服务按调用记录保存 provider、最终 model、Token 与估算成本。费率为 0 时代表未配置估算，不代表免费。 |
| `models.py` | JD/报告数据模型不含供应商绑定，C08-A 无需修改。 |

## Provider Registry

`LLMProvider ← ProviderFactory ← ProviderRegistry`。C08-A 的四家基础见下表。C08-B1 的不可变 `ProviderPreset` 扩展到十家，记录 `provider_id`、显示名、四类主协议、受控官方区域端点、Key 帮助链接、认证方式、候选模型、模型发现／结构化输出／thinking／usage 策略、可选小型 capability adapter、价格来源策略和状态。它不保存用户 Key、Profile 或动态模型目录。模型级验证状态单独由 `ModelCapability` 表达，不能由 Provider 级声明推断。

| ID | 协议 | 模型策略 | C08-A 页面状态 |
|---|---|---|---|
| `deepseek` | OpenAI-compatible Chat | 原 Auto-Safe / pinned | 原页面可用 |
| `openai` | Responses API | 原配置模型 | 原页面可用 |
| `bailian` | OpenAI-compatible Chat | `qwen-plus` 预设；尚无模型发现 | 仅工厂基础，页面未开放 |
| `openrouter` | OpenAI-compatible Chat | 必须显式传模型；不猜测目录 ID | 仅工厂基础，页面未开放 |

百炼是平台 Provider，Qwen 是其模型家族；因此密钥与用量标记使用 `bailian`，模型 ID 可为 `qwen-*`。这四个仅是 C08-A 的基础，不是 C08 的最终供应商范围。C08-B 的 Tier 1 目标为 OpenAI、DeepSeek、百炼、OpenRouter、SiliconFlow、Moonshot/Kimi、Zhipu/GLM、MiniMax、Google Gemini、Anthropic Claude；以后可增加 ModelScope、StepFun、xAI 等。OpenAI 的 Responses API 与 DeepSeek 的专用安全选择具有真实差异，当前不把它们强行迁移到共享适配器。开放范围和引入顺序见 [C08-OSS 研究](c08-open-source-research.md)。

共享 Chat 适配器由预设注入受控 Base URL 和模型；B1 仅按官方文档为 MiniMax 加入 `reasoning_split` 小型适配。DeepSeek 禁用 thinking 的 `extra_body` 留在原有适配器中，避免改变已发布请求格式。Anthropic 与 Gemini 走各自原生 REST 适配器；响应必须通过 `JobAnalysis` 校验。真实模型输出尚未验证。

百炼默认北京公共兼容端点；`BAILIAN_REGION` 只从北京、新加坡、美国弗吉尼亚和香港四个固定区域端点中选择，`BAILIAN_BASE_URL` 仅可覆盖为这四个精确地址，密钥区域必须匹配。workspace 专属域名尚未开放。OpenRouter 使用官方 `https://openrouter.ai/api/v1`，不主动启用自动回退。十家端点、区域、认证和文档来源统一见 [官方 Provider 矩阵](c08-provider-matrix.md)。

## 免费路径、BYOK 和兼容

免费套餐的系统 AI 仅选择 DeepSeek，平台持有 Key，计入系统日额度；没有平台 DeepSeek Key 时继续提供完整本地规则路径。已有非免费套餐的 OpenAI 系统配置与旧 OpenAI 开发者 Key 路径保留。Developer/Admin 的用户 Key 由用户持有，`key_mode=user` 不消耗平台系统额度；B1 页面由十家预设生成统一卡片，分析页只列已保存 Key 且有模型 ID 的 Provider。原 OpenAI/DeepSeek 枚举字符串、关联加密数据、SQLite 记录和 API Key 服务签名不变；旧库约束以事务扩展到十家，不重新加密，也不要求用户迁移 Key。用户偏好单独保存在 `user_provider_profiles`，不重复保存 Key 引用。

模型调用和用量记录仍由 `AIUsageService` 两段处理：预留调用时记录 provider 与选择模型；完成时记录真实 Token、供应商返回的模型和按配置费率计算的估算费用。`api_usage.cost_status=unknown` 与数值 0 一起表示无法估价；只有明确配置了正费率才记 `estimated`。旧记录迁移时保守标为 unknown。跨币种费率需先统一币种，不能直接汇总为同一货币成本。B1 使用 fake SDK/transport 验证协议与存储，未发生真实供应商调用或模型基准测试。

## 安全边界与下一步

本阶段没有自定义任意 Base URL。注册表只接受受控 ID，百炼区域配置只映射到受控端点。C08-B/C 的 Provider Preset 仍只使用官方受控端点；任意自定义端点属于 C08-D，必须先有 SSRF 防护、DNS/IP 重绑定检查、重定向限制、凭证域隔离和审计，再讨论开放。外部模型响应仍作为不可信数据通过 `JobAnalysis` 校验，错误消息不回显凭证。

B1 的原生 HTTP 与 OpenAI SDK 请求均禁用 HTTP 重定向，避免官方端点返回跨域重定向时携带用户 Key 离开受控域名。错误界面只显示脱敏文案；明文 Key 不进入预设、Profile、日志或页面回显。

- **C08-B — Mainstream Provider Presets + Developer BYOK**：以协议而非供应商类为主要适配边界：OpenAI Responses、OpenAI Chat Completions、Anthropic Messages、Gemini API。十家 Tier 1 供应商以受控 preset 加必要的小型 capability adapter 接入 Developer/Admin Key 生命周期与页面；不为每家复制完整 Provider 类。免费用户系统 AI 固定 DeepSeek、BYOK 不消耗 system quota、所有用户 Key 加密；先用 fake 测试并逐模型验证 JSON、Token 与费用，不把未验证能力当生产可用。
- **C08-C — Model Discovery**：`/v1/models` 或官方目录 API、缓存/失效、模型级能力检测及 `verified/unverified`、价格/币种/上下文元数据与来源；不自动把未知模型投入线上。
- **C08-D — Custom Provider**：协议选择、自定义端点、端点探测、连接测试，并在凭证发送前完成服务端 SSRF 防护与审计。生产发布另设隐私、成本、真实沙盒和浏览器回归评审，不与 C08-D 的功能范围混同。

### C08-B1 交付边界

- 统一的合成 JD `test_provider_connection()` 会走真实提取与 `JobAnalysis` 校验，返回认证／请求／Schema／用量／耗时的脱敏结果；仅用户主动点击才可能产生供应商费用。B1 无真实 Key 的验证证据。
- 静态 preset 的端点文档核对、fake 测试和页面配置成功都不等于真实模型 `verified`。新模型标记 `unverified`，实际价格缺失则显示“费用估算未配置”。
- C08-C 的通用模型发现、`/v1/models` 与价格／上下文元数据，C08-D 的 Custom Base URL 均未实现。本地提交不代表生产发布。
