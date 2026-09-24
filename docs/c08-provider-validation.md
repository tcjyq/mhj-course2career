# C08-B2 真实 Provider 兼容性验证

日期：2026-09-23（北京时间）。B1 基线：`f497279e94848472603dd3ed1df266ec4794cbdf`。本轮仅在本地分支验证，未推送或部署。固定输入位于 `tests/fixtures/provider_validation/cases.json`，全部为合成 JD；完整结果仅写入 gitignored `outputs/c08-provider-validation/records.json`，其中没有 Key、请求正文或原始响应。

## 当前实际结果

| Provider | Endpoint ID | Exact model | Protocol | 请求策略 | 凭证存在 | 真实连接 | Fixture | Usage | 结果 |
|---|---|---|---|---|---|---|---:|---|---|
| OpenAI | `global` | `gpt-5.6-luna` | Responses | strict JSON Schema，SDK Pydantic parse | 是 | HTTP 401 / `AUTH_ERROR`，1 次 | 0/4 | 无 | UNKNOWN；未验证 |
| Anthropic | `global` | `claude-haiku-4-5-20251001` | Messages | 原生 `output_config.format` JSON Schema | 是 | HTTP 401 / `AUTH_ERROR`，1 次 | 0/4 | 无 | UNKNOWN；未验证 |
| DeepSeek | `global` | `deepseek-v4-flash` | Chat | JSON object + Pydantic 复核 | 否 | 未请求 | 0/4 | 无 | PENDING |
| 百炼 | `cn-beijing` | `qwen3.8-flash` | Chat | strict JSON Schema 候选 | 否 | 未请求 | 0/4 | 无 | PENDING |
| OpenRouter | `global` | 未选 | Chat | 按精确模型 metadata 判定 | 否 | 未请求 | 0/4 | 无 | PENDING |
| SiliconFlow | `cn` | 未选 | Chat | prompt JSON + Pydantic 复核 | 否 | 未请求 | 0/4 | 无 | PENDING |
| Moonshot | `cn` | 未选 | Chat | prompt JSON + Pydantic 复核 | 否 | 未请求 | 0/4 | 无 | PENDING |
| Zhipu | `cn` | 未选 | Chat | prompt JSON + Pydantic 复核 | 否 | 未请求 | 0/4 | 无 | PENDING |
| MiniMax | `global` | `MiniMax-M3` | Chat | prompt JSON + Pydantic 复核 | 否 | 未请求 | 0/4 | 无 | PENDING |
| Gemini | `global` | 未选 | Native `generateContent` | `responseJsonSchema` 候选 | 否 | 未请求 | 0/4 | 无 | PENDING |

实际外部请求共 **2 次**，均为鉴权失败后的首个连接请求；未触发固定验证集。没有 Provider/model 达到 CONNECTED、SCHEMA_COMPATIBLE 或 VERIFIED。HTTP 401 只证明此运行环境的两份凭证未被对应官方 API 接受，不能证明模型不兼容。没有 usage 回执，因此费用无法估算，也不把缺少费用数据当作免费。记录中的输入、输出 token 均为 0，含义是“无回执”，不是供应商计费确认。

## 契约与判定

`UNKNOWN`：没有成功请求证据；`CONNECTED`：鉴权及请求成功但 JobAnalysis 未通过；`SCHEMA_COMPATIBLE`：单次真实 JobAnalysis 解析通过；`VERIFIED`：连接成功且 4 个固定合成 JD 的技能、反例、逐字 evidence、usage、返回模型与错误处理全部符合要求；`UNSUPPORTED`：已确认该精确模型/协议不能满足必需 schema。HTTP 401 保持 UNKNOWN。验证记录以 Provider × 官方端点 ID × 精确模型为键，不能把一款模型的结果提升到整家 Provider。连接测试最多证明 SCHEMA_COMPATIBLE，永不单次升级为 VERIFIED。

固定集依次检查 SQL、Python/SQL/需求分析、Excel 可选项以及“不要求 Java”的反例，要求每项 `evidence_text` 是输入的原文片段。验证脚本仅执行首个连接请求，并在 schema 和 usage 都通过后逐项继续；出现首个失败便停止。OpenAI SDK 在脚本内关闭自动重试，DeepSeek 脚本禁用备用模型，原生 HTTP 禁止重定向。生产连接测试仍由用户主动点击，失败不会删除个人 Key。

本地执行：

```powershell
.venv\Scripts\python.exe scripts/validate_provider.py --provider bailian --model qwen3.8-flash
.venv\Scripts\python.exe scripts/validate_provider.py --all-available
```

脚本只输出环境变量是否存在；缺凭证会标 PENDING 并跳过。`--all-available` 对有凭证但未确定精确模型的预设要求先用 `--provider --model` 单独验证。OpenRouter 先读取官方模型 metadata 中精确 ID 的 `response_format` 支持，再以 strict `json_schema` 和 `require_parameters` 验证；未获得支持证据时不会升为 VERIFIED。

## 官方机制复核

- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs) 与 [GPT-5.6 Luna](https://developers.openai.com/api/docs/models/gpt-5.6-luna)：Responses `parse` 可由 Pydantic 生成 strict 输出格式；该模型文档列结构化输出支持与每百万 token 标准费率。现有 Responses 生产路径保留。
- [Anthropic Structured Outputs](https://platform.claude.com/docs/en/build-with-claude/structured-outputs)、[Messages API](https://platform.claude.com/docs/en/api/messages/create)、[模型 ID](https://platform.claude.com/docs/en/about-claude/models/model-ids-and-versions)：Claude Haiku 4.5 支持原生 `output_config.format`。`JobAnalysis.model_json_schema()` 含官方不支持的 `minLength`；请求前仅去除该字段，本地仍以完整 Pydantic 模型复核。此次因 401 未能真实证明 schema 可接受。
- [Gemini generateContent](https://ai.google.dev/api/generate-content) 与 [Structured Output](https://ai.google.dev/gemini-api/docs/structured-output)：原生 `responseJsonSchema` 只支持 JSON Schema 子集。`GeminiSchemaAdapter` 从 JobAnalysis schema 删除 `default`、`minLength`、`maxLength`，仍使用原模型校验；待真实 Key 证明请求及模型兼容性。
- [百炼 Structured Output](https://help.aliyun.com/en/model-studio/qwen-structured-output)：`json_object` 只保证 JSON；`json_schema` + `strict:true` 仅限指定 Qwen 系列。默认候选改为文档列出的 `qwen3.8-flash`，请求使用小型严格 schema adapter；区域 Key 和原始 JobAnalysis schema 是否被接受仍待真实验证。
- [DeepSeek JSON Output](https://api-docs.deepseek.com/guides/json_mode/) 与 [Chat API](https://api-docs.deepseek.com/api/create-chat-completion/)：现有 `json_object` 路径保留，能力只标“有效 JSON + Pydantic 后校验”，不标严格 schema。空响应、截断、thinking 禁用、usage 边界有离线回归，真实模型复核待 Key。
- [OpenRouter Structured Outputs](https://openrouter.ai/docs/guides/features/structured-outputs) 与 [Models API](https://openrouter.ai/docs/api/api-reference/models/get-models)：严格 schema 支持由模型决定；需精确 ID 的 metadata、`response_format=json_schema`、`require_parameters:true`，不采用 auto/random。

其他四家 Chat 预设本轮没有对应环境凭证，无法核实账号可用的精确模型、返回模型、usage 或价目，保持 PENDING。错误日志只记录分类与 HTTP 状态；401 的原始消息、URL、请求头和凭证不进入报告。若获得可用凭证，应在本地环境设置变量后按相同 fixture 重跑；不要把完整 Key 发送到聊天或提交到仓库。

价格估算只在拿到 usage 且精确模型匹配时启用：[OpenAI Luna 价格](https://developers.openai.com/api/docs/models/gpt-5.6-luna) 和 [Anthropic 价格](https://platform.claude.com/docs/en/about-claude/pricing) 是脚本中两项静态参考，实际账单、缓存折扣、税费及区域价格仍以供应商为准。C08-C 已在本地另建官方模型目录与能力/价格展示，**没有**补跑 B2 真实模型调用；本表的 B2 结果不变。[C08-C 目录说明](c08-model-discovery.md)。
