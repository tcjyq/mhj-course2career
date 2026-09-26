# C08-B2 真实 Provider 兼容性验证

日期：2026-09-23（北京时间）。B1 基线：`f497279e94848472603dd3ed1df266ec4794cbdf`。本轮仅在本地分支验证，未推送或部署。固定输入位于 `tests/fixtures/provider_validation/cases.json`，全部为合成 JD；完整结果仅写入 gitignored `outputs/c08-provider-validation/records.json`，其中没有 Key、请求正文或原始响应。

## 2026-09-23 历史基线结果

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

当轮实际外部请求共 **2 次**，均为鉴权失败后的首个连接请求；未触发固定验证集。当时没有 Provider/model 达到 CONNECTED、SCHEMA_COMPATIBLE 或 VERIFIED。HTTP 401 只证明当轮环境的两份凭证未被对应官方 API 接受，不能证明模型不兼容。没有 usage 回执，因此费用无法估算，也不把缺少费用数据当作免费。记录中的输入、输出 token 均为 0，含义是“无回执”，不是供应商计费确认。2026-09-26 的新结果见文末。

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

## C08-D0 发布前复核

当时本地 `outputs/c08-provider-validation/records.json` 仍只是忽略版本控制的运行证据；生产模型认证只读取受控版本文件 `src/course2career/verified_models.json`，在 2026-09-24 时为空。连接测试和目录查询均不能写入该认证文件。当轮没有取得大陆 Provider 的完整固定集证据，`VERIFIED` 数量为 0；该数字仅描述历史基线，不代表 2026-09-26 的认证状态。

[Kimi 官方模型列表](https://platform.kimi.com/docs/models) 已明确列出 `kimi-k3`、`kimi-k2.7-code`、`kimi-k2.6` 的精确 ID；[MiniMax 官方 /v1/models 示例](https://platform.minimax.io/docs/api-reference/models/openai/list-models) 列 `MiniMax-M3`。智谱官方页面本次请求超时，静态 `glm-5.1` 仍为未真实验证的候选，发布前需拿官方可用 ID 或授权账号目录再次核对。[C08-D0 持久化说明](c08-production-persistence.md)。

## C08-D1 大陆 Provider 验证门槛

2026-09-24 本机检查结果：DeepSeek、百炼、SiliconFlow 凭证均为 `unavailable`。当轮未调用模型目录或 B2 真实模型接口；DeepSeek 与百炼的精确模型、返回模型、usage、延迟和费用均没有新证据，`VERIFIED` 仍为 0。B2 表中的候选 ID 不等于 D1 已发现或已认证的模型。

2026-09-26 较早的网络续测：本机百炼与 DeepSeek 凭证当时为 `available`（仅核对存在性）。尝试北京 Workspace 官方 `GET /api/v1/models` 查询 `qwen3.8-flash` 时，DNS 与 TCP 443 可达但 TLS 握手 EOF，未获得 HTTP 状态或模型目录；北京通用 DashScope 域名复现相同握手失败，不能据此判断 Key、Workspace 或模型状态。该次百炼目录请求未完成、模型推理请求 0 次、固定合成集未执行、usage 与费用未知；当时仍为 `PENDING`。后续无 VPN 固定集验证结果见文末。

取得本地合法凭证后，先查询官方模型目录，核对鉴权和精确模型可见性。百炼还需核对 Key 的地域、Workspace 和受控 Endpoint 三者一致；不得用北京 Key 请求新加坡端点。随后选成本合适且支持必要结构输出的精确模型，运行 `tests/fixtures/provider_validation/cases.json` 固定合成集，并记录 Provider、Endpoint ID、精确 model ID、schema 策略、返回模型、usage、延迟、脱敏错误、验证版本、fixture 版本与时间。没有 usage 或可信官方价格时，费用为 unknown，不能写 free。

只有项目维护者完成固定真实验证后，才能提交受控 `src/course2career/verified_models.json` 的精确认证记录。用户的“测试连接”只说明个人凭证与所选模型当次可用，不能改写项目认证。D1 的目标是 DeepSeek 与百炼各至少一款精确模型 VERIFIED；当前两条精确模型记录均已通过，仍须等待 D2 发布审查。

## 2026-09-26 C08-D1 百炼 B2 诊断补充（仅本地）

此前无 VPN 的真实运行：`bailian` / `cn-beijing` / `qwen3.8-flash` 的单次连接为 `SCHEMA_COMPATIBLE`；固定 4 题中通过首题，第二题 `case_02_multiple` 停止，记录沿用旧的 `SCHEMA_VALIDATION_FAILED`。旧 `records.json` 没有逐题细节，不能据此判断是 JSON/Pydantic 解析异常、缺技能或 evidence 非原文，更不能宣称该模型不支持 strict JSON Schema。本轮**不重新请求百炼**，不修改已有记录或固定验证标准。

显式执行 `scripts/validate_provider.py` 后，新的 `outputs/c08-provider-validation/fixture_diagnostics.json` 只保留该精确模型已成功解析题目的 `fixture_id`、`passed`、`missing_required_terms`、`present_forbidden_terms` 和 `invalid_evidence_skill_names`（未知技能用 `skill_N` 标识）。不写完整 JD、原始响应、证据正文、Key、Workspace ID 或请求头；同一模型重跑会替换旧逐题诊断，避免误读上次结果。解析成功但固定业务断言失败会记录新的 `FIXTURE_ASSERTION_FAILED`，而解析异常仍保留解析/Schema 错误类别。未执行的题目没有诊断条目，完整 4/4、usage 与返回模型全部符合条件仍是 VERIFIED 的唯一门槛。该诊断功能本身未更新受控认证文件；后续独立真实验证见下节。

## 2026-09-26 C08-D1 精确模型真实验证与认证

本机无 VPN 运行后的本地记录及逐题诊断交叉核对结果：

| Provider | Endpoint ID | Exact model | 策略 | 固定集 | Usage | 请求尝试 | 返回模型 | 错误 | 认证 |
|---|---|---|---|---:|---|---:|---|---|---|
| Bailian | `cn-beijing` | `qwen3.8-flash` | `strict_json_schema` | 4/4 | 有 | 5 | 与请求一致 | 无 | VERIFIED |
| DeepSeek | `global` | `deepseek-flash` | `json_object` | 4/4 | 有 | 5 | 与请求一致 | 无 | VERIFIED |

两条记录均通过 `VerificationRecord` 的完整 VERIFIED 契约，`error_code` 为 null；`fixture_diagnostics.json` 各有 4 条唯一固定题目诊断，均通过且失败列表为空。`summary.md` 仅含最后一次 DeepSeek 运行，不能用它否定此前 Bailian 运行；两条精确认证的依据是本机 `records.json` 与逐题诊断交叉核对。受控 `src/course2career/verified_models.json` 仅纳入上述两个 Provider × 端点 × 精确模型键，未认证其他模型，也不上传忽略目录中的本地证据。费用无可信估算时仍为 unknown。D2 复用这些 D1 证据，没有重新调用真实 Provider；发布候选状态见[候选报告](c08-d2-release-candidate.md)。用户已确认生产 Secrets 保存；其值与运行时效果未核验，`RELEASE_READY=no`。
