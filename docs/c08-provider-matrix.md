# C08-B1 官方 Provider 矩阵

核对日期：2026-09-23。下表的“文档已核对”仅指官方文档中的端点、认证与请求格式；**十家 Provider 均未在本轮使用真实 Key 进行连接或 JobAnalysis 质量验证**。候选模型仅是输入建议，不代表当前账户可用、结构化输出通过或价格已核实。请求 URL 由服务端受控预设拼接；用户只能选择端点 ID，不能输入 Base URL。

| Provider ID | Protocol | Official endpoint / 认证 | Region | Default candidate model | Official docs | Verified status | Notes |
|---|---|---|---|---|---|---|---|
| `openai` | OpenAI Responses | `https://api.openai.com/v1` / Bearer | global | `gpt-5.6-luna`（配置可覆盖） | [Responses API](https://platform.openai.com/docs/api-reference/responses) | 文档已核对；本轮真实调用待验证 | 保留已有 Responses + Pydantic 路径；不套用 Chat adapter。 |
| `deepseek` | OpenAI Chat，现有专用路径 | `https://api.deepseek.com` / Bearer | global | `deepseek-v4-flash`（Auto-Safe） | [Chat Completions](https://api-docs.deepseek.com/api/create-chat-completion) | 文档已核对；本轮真实调用待验证 | 保留白名单、禁用 thinking、404 单次回退；系统 Free 固定此 Provider。 |
| `bailian` | OpenAI Chat | 北京 `https://dashscope.aliyuncs.com/compatible-mode/v1`；新加坡 `https://dashscope-intl.aliyuncs.com/compatible-mode/v1`；弗吉尼亚 `https://dashscope-us.aliyuncs.com/compatible-mode/v1`；香港 `https://cn-hongkong.dashscope.aliyuncs.com/compatible-mode/v1` / Bearer | `cn-beijing`、`ap-southeast-1`、`us-east-1`、`cn-hongkong` | `qwen-plus` | [区域与 Base URL](https://help.aliyun.com/en/model-studio/base-url) · [OpenAI 兼容](https://help.aliyun.com/en/model-studio/compatibility-of-openai-with-dashscope) | 文档已核对；本轮真实调用待验证 | Key 须与区域匹配；workspace 专属域名尚未开放。 |
| `openrouter` | OpenAI Chat | `https://openrouter.ai/api/v1` / Bearer | global | 无，手填官方模型 ID | [Quickstart](https://openrouter.ai/docs/quickstart) | 文档已核对；本轮真实调用待验证 | 不主动启用自动路由或备用模型；实际模型提供方和成本随选择变化。 |
| `siliconflow` | OpenAI Chat | `https://api.siliconflow.cn/v1` / Bearer | cn | 无，手填官方模型 ID | [Chat API](https://docs.siliconflow.cn/docs/api/chat-completions-post) | 文档已核对；本轮真实调用待验证 | 官方模型目录会变化，B1 不内置完整目录。 |
| `moonshot` | OpenAI Chat | `https://api.moonshot.cn/v1` / Bearer | cn | 无，手填官方模型 ID | [Kimi 官方平台入门](https://platform.kimi.com/blog/posts/kimi-api-quick-start-guide) | 文档已核对；本轮真实调用待验证 | 端点证据来自平台文章；当前模型 ID 需用户按官方控制台确认。 |
| `zhipu` | OpenAI Chat | `https://open.bigmodel.cn/api/paas/v4` / Bearer | cn | 无，手填官方模型 ID | [智谱官方示例](https://docs.bigmodel.cn/cn/best-practice/case/ai-search-engine) | 文档已核对；本轮真实调用待验证 | 预设仅供官方 Chat Completions 路径；具体模型能力未统一验证。 |
| `minimax` | OpenAI Chat | `https://api.minimax.io/v1` / Bearer | global | `MiniMax-M3` | [OpenAI SDK 兼容](https://platform.minimax.io/docs/api-reference/text-openai-api) | 文档已核对；本轮真实调用待验证 | 仅加 `reasoning_split` 小型适配；输出仍由本地 JobAnalysis 校验。 |
| `gemini` | Gemini Native | `https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent` / `x-goog-api-key` | global | 无，手填官方模型 ID | [Gemini API](https://ai.google.dev/api) · [generateContent](https://ai.google.dev/api/generate-content) | 文档已核对；本轮真实调用待验证 | 请求 JSON MIME，不能据此认定任意模型已通过结构化提取。 |
| `anthropic` | Anthropic Messages | `https://api.anthropic.com/v1/messages` / `x-api-key` + `anthropic-version` | global | 无，手填官方模型 ID | [Messages API](https://platform.claude.com/docs/en/api/messages/create) | 文档已核对；本轮真实调用待验证 | B1 用 prompt JSON + 本地严格校验；不宣称原生严格 `json_schema`。 |

OpenAI、DeepSeek 仍沿用当前部署配置中的模型名和成本参数。其他 Provider 只有用户自行确认了模型 ID 才能分析；默认费率缺失时记录 `cost_status=unknown`，页面显示“费用估算未配置”。百炼和 OpenRouter 虽保留既有配置费率入口，费率为零时仍视为未知。价格、币种、上下文窗口和模型级能力来源将由 C08-C 完成。

本矩阵只允许账号持有人自己的 API Key 进入相应官方域名。B1 无真实 Key 调用结果，连接测试由用户明确点击后才会发起可能计费的合成 JD 请求。模型级 `verified` 不能由端点文档、preset 或 fake 测试推断；新增模型均保持 `unverified`。仓库既有 DeepSeek 白名单沿用此前专用兼容策略，仍需对当前模型和账号另做真实复核。
