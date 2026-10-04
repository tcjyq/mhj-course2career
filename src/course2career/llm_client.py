from pathlib import Path
from typing import Any

from course2career.config import Settings
from course2career.llm_provider import LLMUsage, ProviderName, coerce_token_count
from course2career.models import JobAnalysis
from course2career.provider_registry import get_provider_preset
from course2career.provider_runtime import ProviderRuntime, returned_model_id

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "extract_jd_skills.txt"


class LLMClientError(RuntimeError):
    """大模型调用失败，且不暴露供应商或凭证细节。"""


class OpenAIJDClient(ProviderRuntime):
    """使用 OpenAI Responses API 返回结构化岗位技能。"""

    def __init__(
        self,
        settings: Settings,
        sdk_client: Any | None = None,
        max_output_tokens: int = 1500,
        max_retries: int = 0,
    ) -> None:
        if not settings.openai_api_key:
            raise LLMClientError("未配置 OPENAI_API_KEY，无法启用 AI 分析模式。")
        if max_retries != 0:
            raise LLMClientError("自动 SDK 重试未开放，请使用受控调用预算。")
        self.settings = settings
        self.max_output_tokens = max(int(max_output_tokens), 1)
        self._last_usage: LLMUsage | None = None
        endpoint = get_provider_preset(ProviderName.OPENAI).base_url
        self._init_runtime(settings.openai_model, settings.openai_model, endpoint)
        if sdk_client is None:
            try:
                from openai import DefaultHttpxClient, OpenAI
            except ImportError as exc:
                raise LLMClientError(
                    "未安装 OpenAI SDK，无法启用 AI 分析模式。"
                ) from exc
            sdk_client = OpenAI(
                api_key=settings.openai_api_key,
                base_url=endpoint,
                timeout=settings.openai_timeout_seconds,
                max_retries=max_retries,
                http_client=DefaultHttpxClient(follow_redirects=False),
            )
        self.client = sdk_client

    @property
    def provider_name(self) -> ProviderName:
        return ProviderName.OPENAI

    @property
    def model_name(self) -> str:
        return self.settings.openai_model

    @property
    def last_usage(self) -> LLMUsage | None:
        return self._last_usage

    def extract_job_skills(self, jd_text: str) -> JobAnalysis:
        self._begin_call(self.model_name)
        try:
            raw = self.client.responses.with_raw_response.parse(
                model=self.settings.openai_model,
                instructions=PROMPT_PATH.read_text(encoding="utf-8"),
                input=jd_text,
                text_format=JobAnalysis,
                max_output_tokens=self.max_output_tokens,
            )
            self._observe_response(None)
            payload = raw.http_response.json()
            if not isinstance(payload, dict):
                raise ValueError("invalid response object")
            self._observe_response(payload.get("model"))
            usage = payload.get("usage")
            if isinstance(usage, dict):
                self._last_usage = LLMUsage(
                    input_tokens=coerce_token_count(usage.get("input_tokens", 0)),
                    output_tokens=coerce_token_count(usage.get("output_tokens", 0)),
                    model=returned_model_id(payload.get("model"))
                    or self.settings.openai_model,
                )
            # SDK validation runs only after identity and billable usage are observed.
            response = raw.parse()
            result = response.output_parsed
            if result is None:
                raise ValueError("empty structured output")
            return self._finish_call(result.model_copy(update={"source": "ai"}))
        except LLMClientError:
            raise
        except Exception as exc:
            self._fail_attempt(exc, schema_requested=True)
            raise LLMClientError(
                "大模型服务暂时不可用，请稍后重试或切换到本地规则模式。"
            ) from exc
