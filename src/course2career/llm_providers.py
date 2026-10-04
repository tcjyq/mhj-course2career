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
from course2career.provider_registry import (
    ProviderPreset,
    ProviderProtocol,
    get_provider_preset,
)
from course2career.provider_runtime import ProviderRuntime, returned_model_id
from course2career.structured_output import (
    BailianSchemaAdapter,
    StructuredOutputStrategy,
)

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "extract_jd_skills.txt"
DEEPSEEK_MODELS = APPROVED_DEEPSEEK_MODELS


class ProviderError(LLMClientError):
    """模型供应商配置或调用失败。"""


class OpenAICompatibleChatProvider(ProviderRuntime):
    """供新预设复用的 Chat Completions 适配器。"""

    def __init__(
        self,
        *,
        preset: ProviderPreset,
        api_key: str,
        model: str,
        endpoint_id: str | None = None,
        timeout_seconds: float = 30,
        sdk_client: Any | None = None,
        max_output_tokens: int = 1500,
        structured_strategy: StructuredOutputStrategy | None = None,
        max_retries: int = 0,
    ) -> None:
        if not api_key or not model or not model.strip() or len(model) > 200:
            raise ProviderError("模型或开发者API Key配置无效。")
        if max_retries != 0:
            raise ProviderError("自动 SDK 重试未开放，请使用受控调用预算。")
        if preset.primary_protocol != ProviderProtocol.OPENAI_CHAT:
            raise ProviderError("模型供应商协议配置无效。")
        try:
            endpoint = preset.endpoint(endpoint_id or preset.selected_endpoint_id)
        except ValueError as exc:
            raise ProviderError(str(exc)) from exc
        self.preset = preset
        self.model = model.strip()
        self.max_output_tokens = max(int(max_output_tokens), 1)
        self.structured_strategy = structured_strategy
        self._last_usage: LLMUsage | None = None
        self._init_runtime(model, self.model, endpoint)
        if sdk_client is None:
            try:
                from openai import DefaultHttpxClient, OpenAI
            except ImportError as exc:
                raise ProviderError("未安装OpenAI兼容SDK。") from exc
            sdk_client = OpenAI(
                api_key=api_key,
                base_url=endpoint,
                timeout=timeout_seconds,
                max_retries=max_retries,
                http_client=DefaultHttpxClient(follow_redirects=False),
            )
        self.client = sdk_client

    @property
    def provider_name(self) -> ProviderName:
        return self.preset.provider_id

    @property
    def model_name(self) -> str:
        return self.model

    @property
    def last_usage(self) -> LLMUsage | None:
        return self._last_usage

    def extract_job_skills(self, jd_text: str) -> JobAnalysis:
        self._begin_call(self.model)
        schema = json.dumps(
            JobAnalysis.model_json_schema(), ensure_ascii=False, separators=(",", ":")
        )
        instructions = (
            PROMPT_PATH.read_text(encoding="utf-8")
            + "\n请只输出JSON对象，不要使用Markdown代码块。JSON Schema："
            + schema
        )
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": instructions},
                {"role": "user", "content": jd_text},
            ],
            "max_tokens": self.max_output_tokens,
            "stream": False,
        }
        strategy = self.structured_strategy or self.preset.strategy_for_model(
            self.model
        )
        if strategy == StructuredOutputStrategy.JSON_OBJECT:
            kwargs["response_format"] = {"type": "json_object"}
        elif strategy == StructuredOutputStrategy.STRICT_JSON_SCHEMA:
            kwargs["response_format"] = {
                "type": "json_schema",
                "json_schema": {
                    "name": "job_analysis",
                    "strict": True,
                    "schema": BailianSchemaAdapter.job_analysis_schema(),
                },
            }
        extra_body = self.preset.compatibility.extra_body(strategy)
        if extra_body:
            kwargs["extra_body"] = extra_body
        try:
            response = self.client.chat.completions.create(**kwargs)
            self._observe_response(getattr(response, "model", None))
            usage = getattr(response, "usage", None)
            if usage is not None:
                self._last_usage = LLMUsage(
                    input_tokens=coerce_token_count(getattr(usage, "prompt_tokens", 0)),
                    output_tokens=coerce_token_count(
                        getattr(usage, "completion_tokens", 0)
                    ),
                    model=_safe_optional_text(getattr(response, "model", None))
                    or self.model,
                    system_fingerprint=_safe_optional_text(
                        getattr(response, "system_fingerprint", None)
                    ),
                )
            content = response.choices[0].message.content
            if not content:
                raise ValueError("empty response content")
            return self._finish_call(
                JobAnalysis.model_validate_json(content).model_copy(
                    update={"source": "ai"}
                )
            )
        except Exception as exc:
            self._fail_attempt(
                exc,
                schema_requested=strategy
                == StructuredOutputStrategy.STRICT_JSON_SCHEMA,
            )
            raise ProviderError("模型服务暂时不可用，请检查配置后重试。") from exc


class DeepSeekProvider(ProviderRuntime):
    """通过DeepSeek的OpenAI兼容Chat Completions接口提取岗位技能。"""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "deepseek-flash",
        fallback_models: tuple[str, ...] = (),
        max_output_tokens: int = 1500,
        timeout_seconds: float = 30,
        sdk_client: Any | None = None,
        max_retries: int = 0,
        saved_model: str | None = None,
    ) -> None:
        if not api_key:
            raise ProviderError("未配置 DeepSeek API Key。")
        if max_retries != 0:
            raise ProviderError("自动 SDK 重试未开放，请使用受控调用预算。")
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
        self._init_runtime(
            saved_model if saved_model is not None else model,
            model,
            DEEPSEEK_BASE_URL,
            max_attempts=2 if self.fallback_models else 1,
        )
        if sdk_client is None:
            try:
                from openai import DefaultHttpxClient, OpenAI
            except ImportError as exc:
                raise ProviderError("未安装OpenAI兼容SDK。") from exc
            sdk_client = OpenAI(
                api_key=api_key,
                base_url=DEEPSEEK_BASE_URL,
                timeout=timeout_seconds,
                max_retries=max_retries,
                http_client=DefaultHttpxClient(follow_redirects=False),
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
        self._begin_call(self.model)
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
            self._fail_attempt(exc)
            if _is_missing_model_error(exc) and self.fallback_models:
                self.model = self.fallback_models[0]
                self._start_attempt(self.model, "MODEL_NOT_FOUND")
                try:
                    response = self._create_completion(
                        self.model,
                        messages=[
                            {"role": "system", "content": instructions},
                            {"role": "user", "content": jd_text},
                        ],
                    )
                except Exception as fallback_exc:
                    self._fail_attempt(fallback_exc)
                    raise ProviderError(
                        "DeepSeek服务暂时不可用，请检查配置后重试。"
                    ) from fallback_exc
            else:
                raise ProviderError(
                    "DeepSeek服务暂时不可用，请检查配置后重试。"
                ) from exc

        try:
            self._observe_response(getattr(response, "model", None))
            usage = getattr(response, "usage", None)
            if usage is not None:
                actual_model = returned_model_id(getattr(response, "model", None))
                self._last_usage = LLMUsage(
                    input_tokens=coerce_token_count(getattr(usage, "prompt_tokens", 0)),
                    output_tokens=coerce_token_count(
                        getattr(usage, "completion_tokens", 0)
                    ),
                    model=actual_model or self.model,
                    system_fingerprint=_safe_optional_text(
                        getattr(response, "system_fingerprint", None)
                    ),
                )
            content = response.choices[0].message.content
            if not content:
                raise ValueError("empty response content")
            result = JobAnalysis.model_validate_json(content)
            return self._finish_call(result.model_copy(update={"source": "ai"}))
        except ProviderError:
            raise
        except Exception as exc:
            self._fail_attempt(exc)
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
            extra_body=get_provider_preset(
                ProviderName.DEEPSEEK
            ).compatibility.extra_body(StructuredOutputStrategy.JSON_OBJECT),
        )


def _is_missing_model_error(exc: Exception) -> bool:
    return getattr(exc, "status_code", None) == 404


def _safe_optional_text(value: object) -> str | None:
    return returned_model_id(value)
