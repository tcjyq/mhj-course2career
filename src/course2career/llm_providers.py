import json
from pathlib import Path
from typing import Any

from course2career.llm_client import LLMClientError
from course2career.llm_provider import LLMUsage, ProviderName, coerce_token_count
from course2career.model_catalog import (
    APPROVED_DEEPSEEK_MODELS,
    DEEPSEEK_BASE_URL,
)
from course2career.models import JobAnalysis

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "extract_jd_skills.txt"
DEEPSEEK_MODELS = APPROVED_DEEPSEEK_MODELS


class ProviderError(LLMClientError):
    """模型供应商配置或调用失败。"""


class DeepSeekProvider:
    """通过DeepSeek的OpenAI兼容Chat Completions接口提取岗位技能。"""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "deepseek-v4-flash",
        fallback_models: tuple[str, ...] = (),
        max_output_tokens: int = 1500,
        timeout_seconds: float = 30,
        sdk_client: Any | None = None,
    ) -> None:
        if not api_key:
            raise ProviderError("未配置 DeepSeek API Key。")
        if model not in DEEPSEEK_MODELS:
            raise ProviderError("不支持的 DeepSeek 模型。")
        invalid_fallbacks = set(fallback_models) - DEEPSEEK_MODELS
        if invalid_fallbacks:
            raise ProviderError("备用 DeepSeek 模型尚未通过兼容性验证。")
        self.model = model
        self.fallback_models = tuple(
            candidate for candidate in fallback_models if candidate != model
        )
        self.max_output_tokens = max(int(max_output_tokens), 1)
        self._last_usage: LLMUsage | None = None
        if sdk_client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise ProviderError("未安装OpenAI兼容SDK。") from exc
            sdk_client = OpenAI(
                api_key=api_key,
                base_url=DEEPSEEK_BASE_URL,
                timeout=timeout_seconds,
            )
        self.client = sdk_client

    @property
    def provider_name(self) -> ProviderName:
        return ProviderName.DEEPSEEK

    @property
    def model_name(self) -> str:
        return self.model

    @property
    def last_usage(self) -> LLMUsage | None:
        return self._last_usage

    def extract_job_skills(self, jd_text: str) -> JobAnalysis:
        self._last_usage = None
        schema = json.dumps(
            JobAnalysis.model_json_schema(), ensure_ascii=False, separators=(",", ":")
        )
        instructions = (
            PROMPT_PATH.read_text(encoding="utf-8")
            + "\n请只输出JSON对象，不要使用Markdown代码块。JSON Schema："
            + schema
        )
        try:
            response = self._create_completion(
                self.model,
                messages=[
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": jd_text},
                ],
            )
        except Exception as exc:
            if _is_missing_model_error(exc) and self.fallback_models:
                self.model = self.fallback_models[0]
                try:
                    response = self._create_completion(
                        self.model,
                        messages=[
                            {"role": "system", "content": instructions},
                            {"role": "user", "content": jd_text},
                        ],
                    )
                except Exception as fallback_exc:
                    raise ProviderError(
                        "DeepSeek服务暂时不可用，请检查配置后重试。"
                    ) from fallback_exc
            else:
                raise ProviderError(
                    "DeepSeek服务暂时不可用，请检查配置后重试。"
                ) from exc

        try:
            usage = getattr(response, "usage", None)
            if usage is not None:
                response_model = getattr(response, "model", None)
                actual_model = (
                    response_model if response_model in DEEPSEEK_MODELS else self.model
                )
                self._last_usage = LLMUsage(
                    input_tokens=coerce_token_count(getattr(usage, "prompt_tokens", 0)),
                    output_tokens=coerce_token_count(
                        getattr(usage, "completion_tokens", 0)
                    ),
                    model=actual_model,
                    system_fingerprint=_safe_optional_text(
                        getattr(response, "system_fingerprint", None)
                    ),
                )
            content = response.choices[0].message.content
            if not content:
                raise ValueError("empty response content")
            result = JobAnalysis.model_validate_json(content)
            return result.model_copy(update={"source": "ai"})
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError("DeepSeek服务暂时不可用，请检查配置后重试。") from exc

    def _create_completion(
        self,
        model: str,
        *,
        messages: list[dict[str, str]],
    ) -> Any:
        return self.client.chat.completions.create(
            model=model,
            messages=messages,
            response_format={"type": "json_object"},
            max_tokens=self.max_output_tokens,
            stream=False,
            extra_body={"thinking": {"type": "disabled"}},
        )


def _is_missing_model_error(exc: Exception) -> bool:
    return getattr(exc, "status_code", None) == 404


def _safe_optional_text(value: object) -> str | None:
    if not isinstance(value, str):
        return None
    value = value.strip()
    return value[:200] or None
