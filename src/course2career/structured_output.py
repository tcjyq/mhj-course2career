"""按协议声明输出约束；实际验证状态单独由验证记录决定。"""

from enum import StrEnum
from typing import Any

from course2career.models import JobAnalysis


class StructuredOutputStrategy(StrEnum):
    STRICT_JSON_SCHEMA = "strict_json_schema"
    JSON_OBJECT = "json_object"
    NATIVE_SCHEMA = "native_schema"
    TOOL_SCHEMA = "tool_schema"
    PROMPT_JSON = "prompt_json"
    NONE = "none"


def _without_unsupported(schema: Any, keys: frozenset[str]) -> Any:
    if isinstance(schema, list):
        return [_without_unsupported(item, keys) for item in schema]
    if isinstance(schema, dict):
        return {
            key: _without_unsupported(value, keys)
            for key, value in schema.items()
            if key not in keys
        }
    return schema


class AnthropicSchemaAdapter:
    """原生 JSON Schema 不接受字符串长度限制；本地仍用原模型复核。"""

    @staticmethod
    def job_analysis_schema() -> dict[str, Any]:
        return _without_unsupported(
            JobAnalysis.model_json_schema(), frozenset({"minLength", "maxLength"})
        )


class GeminiSchemaAdapter:
    """将 Pydantic schema 缩至 Gemini responseJsonSchema 支持的字段。"""

    @staticmethod
    def job_analysis_schema() -> dict[str, Any]:
        return _without_unsupported(
            JobAnalysis.model_json_schema(),
            frozenset({"default", "minLength", "maxLength"}),
        )


class BailianSchemaAdapter:
    """为受控 Qwen strict 模式补齐必填字段，原模型继续做本地校验。"""

    @staticmethod
    def job_analysis_schema() -> dict[str, Any]:
        schema = _without_unsupported(
            JobAnalysis.model_json_schema(),
            frozenset({"default", "minLength", "maxLength"}),
        )
        for obj in [schema, *schema.get("$defs", {}).values()]:
            if obj.get("type") == "object":
                obj["required"] = list(obj.get("properties", {}))
                obj["additionalProperties"] = False
        return schema
