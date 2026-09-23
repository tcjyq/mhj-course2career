"""Anthropic Messages 与 Gemini Native 的轻量协议适配器。"""

import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any
from urllib.request import HTTPRedirectHandler, Request, build_opener

from course2career.llm_provider import LLMUsage, ProviderName, coerce_token_count
from course2career.llm_providers import ProviderError
from course2career.models import JobAnalysis
from course2career.provider_registry import ProviderPreset, ProviderProtocol

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "extract_jd_skills.txt"
NativeTransport = Callable[[str, dict[str, str], dict[str, Any], float], dict[str, Any]]
MODEL_SEGMENT = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,199}\Z")


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request: Request, *args: Any) -> None:
        return None


def _post_json(
    url: str, headers: dict[str, str], body: dict[str, Any], timeout: float
) -> dict[str, Any]:
    request = Request(
        url,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={**headers, "Content-Type": "application/json"},
        method="POST",
    )
    with build_opener(_NoRedirect).open(request, timeout=timeout) as response:
        payload = response.read(1_000_001)
    if len(payload) > 1_000_000:
        raise ValueError("response too large")
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise ValueError("invalid response object")
    return parsed


def _instructions() -> str:
    schema = json.dumps(
        JobAnalysis.model_json_schema(), ensure_ascii=False, separators=(",", ":")
    )
    return (
        PROMPT_PATH.read_text(encoding="utf-8")
        + "\n请只输出符合以下JSON Schema的对象，不要使用Markdown代码块。"
        + schema
    )


class AnthropicMessagesProvider:
    """原生 /v1/messages；结构化输出采用提示词加本地严格校验。"""

    def __init__(
        self,
        *,
        preset: ProviderPreset,
        api_key: str,
        model: str,
        endpoint_id: str | None = None,
        timeout_seconds: float = 30,
        transport: NativeTransport = _post_json,
    ) -> None:
        if preset.primary_protocol != ProviderProtocol.ANTHROPIC_MESSAGES:
            raise ProviderError("模型供应商协议配置无效。")
        if not api_key or not model.strip() or len(model) > 200:
            raise ProviderError("模型或开发者API Key配置无效。")
        self.preset = preset
        self.model = model.strip()
        self.endpoint = preset.endpoint(endpoint_id or preset.selected_endpoint_id)
        self.timeout_seconds = timeout_seconds
        self.transport = transport
        self._api_key = api_key
        self._last_usage: LLMUsage | None = None

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
        self._last_usage = None
        try:
            response = self.transport(
                self.endpoint.rstrip("/") + "/v1/messages",
                {
                    "x-api-key": self._api_key,
                    "anthropic-version": "2023-06-01",
                },
                {
                    "model": self.model,
                    "max_tokens": 1500,
                    "system": _instructions(),
                    "messages": [{"role": "user", "content": jd_text}],
                },
                self.timeout_seconds,
            )
            usage = response.get("usage")
            if isinstance(usage, dict):
                self._last_usage = LLMUsage(
                    input_tokens=coerce_token_count(usage.get("input_tokens")),
                    output_tokens=coerce_token_count(usage.get("output_tokens")),
                    model=_model_name(response.get("model"), self.model),
                )
            blocks = response["content"]
            content = "".join(
                block["text"]
                for block in blocks
                if isinstance(block, dict) and block.get("type") == "text"
            )
            return JobAnalysis.model_validate_json(content).model_copy(
                update={"source": "ai"}
            )
        except Exception as exc:
            self._last_usage = None
            raise ProviderError("模型服务暂时不可用，请检查配置后重试。") from exc


class GeminiProvider:
    """原生 generateContent；JSON MIME 是请求策略，非模型已验证声明。"""

    def __init__(
        self,
        *,
        preset: ProviderPreset,
        api_key: str,
        model: str,
        endpoint_id: str | None = None,
        timeout_seconds: float = 30,
        transport: NativeTransport = _post_json,
    ) -> None:
        if preset.primary_protocol != ProviderProtocol.GEMINI_NATIVE:
            raise ProviderError("模型供应商协议配置无效。")
        if not api_key or not MODEL_SEGMENT.fullmatch(model):
            raise ProviderError("模型或开发者API Key配置无效。")
        self.preset = preset
        self.model = model
        self.endpoint = preset.endpoint(endpoint_id or preset.selected_endpoint_id)
        self.timeout_seconds = timeout_seconds
        self.transport = transport
        self._api_key = api_key
        self._last_usage: LLMUsage | None = None

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
        self._last_usage = None
        try:
            response = self.transport(
                self.endpoint.rstrip("/") + f"/models/{self.model}:generateContent",
                {"x-goog-api-key": self._api_key},
                {
                    "systemInstruction": {"parts": [{"text": _instructions()}]},
                    "contents": [{"role": "user", "parts": [{"text": jd_text}]}],
                    "generationConfig": {
                        "responseMimeType": "application/json",
                    },
                },
                self.timeout_seconds,
            )
            usage = response.get("usageMetadata")
            if isinstance(usage, dict):
                self._last_usage = LLMUsage(
                    input_tokens=coerce_token_count(usage.get("promptTokenCount")),
                    output_tokens=coerce_token_count(usage.get("candidatesTokenCount")),
                    model=_model_name(response.get("modelVersion"), self.model),
                )
            parts = response["candidates"][0]["content"]["parts"]
            content = "".join(
                part["text"]
                for part in parts
                if isinstance(part, dict) and isinstance(part.get("text"), str)
            )
            return JobAnalysis.model_validate_json(content).model_copy(
                update={"source": "ai"}
            )
        except Exception as exc:
            self._last_usage = None
            raise ProviderError("模型服务暂时不可用，请检查配置后重试。") from exc


def _model_name(value: object, fallback: str) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()[:200]
    return fallback
