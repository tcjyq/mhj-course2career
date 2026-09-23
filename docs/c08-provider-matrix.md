# C08-B2 官方 Provider 矩阵

核对日期：2026-09-23。仅 OpenAI 与 Anthropic 在 B2 收到真实环境凭证，分别向官方 API 发出 1 次连接请求，均返回 HTTP 401；其余八家无凭证、未请求。**没有模型通过真实兼容性验证。** 候选模型不代表账户可用或价格已核实。请求 URL 由服务端受控预设拼接；用户只能选择端点 ID，不能输入 Base URL。详细证据见 [C08-B2 验证记录](c08-provider-validation.md)。

| Provider ID | Protocol | Official endpoint / 认证 | Region | Default candidate model | Official docs | Verified status | Notes |
|---|---|---|---|---|---|---|---|
| `openai` | OpenAI Responses | `https://api.openai.com/v1` / Bearer | global | `gpt-5.6-luna`（配置可覆盖） | [Responses API](https://developers.openai.com/api/docs/guides/structured-outputs) | 1 次真实请求，401 `AUTH_ERROR`；UNKNOWN | 保留 Responses + Pydantic 路径；未进入 fixture。 |
| `deepseek` | OpenAI Chat，现有专用路径 | `https://api.deepseek.com` / Bearer | global | `deepseek-v4-flash`（Auto-Safe） | [JSON Output](https://api-docs.deepseek.com/guides/json_mode/) | 无 Key；PENDING | JSON object + Pydantic 后校验，不等于 strict schema；系统 Free 固定此 Provider。 |
| `bailian` | OpenAI Chat | 北京 `https://dashscope.aliyuncs.com/compatible-mode/v1`；新加坡 `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`；弗吉尼亚 `https://dashscope-us.aliyuncs.com/compatible-mode/v1`；香港 `https://cn-hongkong.dashscope.aliyuncs.com/compatible-mode/v1` / Bearer | `cn-beijing`、`ap-southeast-1`、`us-east-1`、`cn-hongkong` | `qwen3.8-flash` | [区域与 Base URL](https://help.aliyun.com/en/model-studio/base-url) · [Structured Output](https://help.aliyun.com/en/model-studio/qwen-structured-output) | 无 Key；PENDING | 支持模型候选使用 strict `json_schema`；Key 须与区域匹配。 |
| `openrouter` | OpenAI Chat | `https://openrouter.ai/api/v1` / Bearer | global | 无，手填官方模型 ID | [Structured Outputs](https://openrouter.ai/docs/guides/features/structured-outputs) | 无 Key；PENDING | `VERIFIED` 前须精确模型 metadata 支持 schema，并以 `require_parameters:true` 验证；不使用 auto/random。 |
| `siliconflow` | OpenAI Chat | `https://api.siliconflow.cn/v1` / Bearer | cn | 无，手填官方模型 ID | [Chat API](https://docs.siliconflow.cn/docs/api/chat-completions-post) | 无 Key；PENDING | 现用 prompt JSON + 本地校验，实际模型能力待核实。 |
| `moonshot` | OpenAI Chat | `https://api.moonshot.cn/v1` / Bearer | cn | 无，手填官方模型 ID | [Kimi 官方平台入门](https://platform.kimi.com/blog/posts/kimi-api-quick-start-guide) | 无 Key；PENDING | 实际模型 ID 与 usage 待核实。 |
| `zhipu` | OpenAI Chat | `https://open.bigmodel.cn/api/paas/v4` / Bearer | cn | 无，手填官方模型 ID | [智谱官方示例](https://docs.bigmodel.cn/cn/best-practice/case/ai-search-engine) | 无 Key；PENDING | 预设仅供官方 Chat Completions 路径，实际模型能力待核实。 |
| `minimax` | OpenAI Chat | `https://api.minimax.io/v1` / Bearer | global | `MiniMax-M3` | [OpenAI SDK 兼容](https://platform.minimax.io/docs/api-reference/text-openai-api) | 无 Key；PENDING | 仅加 `reasoning_split` 小型适配；实际模型能力待核实。 |
| `gemini` | Gemini Native | `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` / `x-goog-api-key` | global | 无，手填官方模型 ID | [generateContent](https://ai.google.dev/api/generate-content) | 无 Key；PENDING | 使用 `responseJsonSchema` 与 schema 子集 adapter，待真实验证。 |
| `anthropic` | Anthropic Messages | `https://api.anthropic.com/v1/messages` / `x-api-key` + `anthropic-version` | global | 无；B2 选 `claude-haiku-4-5-20251001` | [Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs) | 1 次真实请求，401 `AUTH_ERROR`；UNKNOWN | B2 已改原生 `output_config.format`，但鉴权失败使 schema 实测仍待完成。 |

OpenAI、DeepSeek 仍沿用当前部署配置中的模型名和成本参数。其他 Provider 只有用户自行确认模型 ID 才能分析；默认费率缺失时记录 `cost_status=unknown`，页面显示“费用估算未配置”。百炼和 OpenRouter 虽保留既有配置费率入口，费率为零时仍视为未知。价格、币种、上下文窗口和模型级能力来源将由 C08-C 完成。

本矩阵只允许账号持有人自己的 API Key 进入相应官方域名。页面连接测试由用户主动点击后发送合成 JD。模型级 `verified` 只能来自完整真实 fixture 证据；当前均为 `unknown`。DeepSeek 历史 Auto-Safe 白名单只用于生产自动选择范围，不代表本轮精确模型已获得 B2 `VERIFIED` 状态。
