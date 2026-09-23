# ADR 004：以精确模型真实证据决定验证状态

日期：2026-09-23。状态：已采纳（C08-B2，本地分支）。

## 背景

C08-B1 的十家预设和 fake 契约测试只证明接口形状；`DeepSeek` 历史 Auto-Safe 白名单曾在 UI 中被显示为 VERIFIED，容易与当前真实兼容性混淆。不同供应商对 JSON object、严格 JSON Schema 和原生结构化输出的支持也不同，且往往依赖精确模型。

## 决定

将输出策略 `STRICT_JSON_SCHEMA`、`JSON_OBJECT`、`NATIVE_SCHEMA`、`TOOL_SCHEMA`、`PROMPT_JSON`、`NONE` 与真实验证状态独立建模。验证状态为 `UNKNOWN`、`CONNECTED`、`SCHEMA_COMPATIBLE`、`VERIFIED`、`UNSUPPORTED`，按 Provider × 受控端点 ID × 精确模型存储。`VERIFIED` 只由 4 个固定合成 JD 全部通过技能、反例、原文 evidence、JobAnalysis、usage 和返回模型检查产生；一次连接成功不能产生该状态。无有效凭证或 401 保持 UNKNOWN，不推断模型不支持。

Anthropic 与 Gemini 采用各自原生 schema 参数；百炼受支持的 Qwen Flash 使用 strict Chat schema；DeepSeek 仍用 JSON object 和完整 Pydantic 后校验。Schema adapter 只删除供应商不支持的约束并保留原始 JobAnalysis 作本地验证。OpenRouter 必须先有精确模型 metadata 支持证据，再用 strict schema 与 `require_parameters:true` 验证。真实记录仅写入 gitignored 本地 JSON，安全摘要可进入文档；CI 只运行 mock。

## 结果与边界

状态语义不再继承旧白名单；生产 Auto-Safe 的批准范围仍按既有机制运行。当前 OpenAI/Anthropic 各一次真实请求均 401，未获得 VERIFIED。验证记录是本地开发证据，不是对其他账号、价格或未来模型版本的永久保证；C08-C 负责动态发现、能力和价格元数据。详见 [B2 验证报告](../c08-provider-validation.md)。
