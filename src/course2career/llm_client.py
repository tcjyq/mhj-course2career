from pathlib import Path
from typing import Any

from course2career.config import Settings
from course2career.llm_provider import LLMUsage, ProviderName, coerce_token_count
from course2career.models import JobAnalysis

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "extract_jd_skills.txt"


class LLMClientError(RuntimeError):
    """大模型调用失败，且不暴露供应商或凭证细节。"""


class OpenAIJDClient:
    """使用 OpenAI Responses API 返回结构化岗位技能。"""

    def __init__(self, settings: Settings, sdk_client: Any | None = None) -> None:
        if not settings.openai_api_key:
            raise LLMClientError("未配置 OPENAI_API_KEY，无法启用 AI 分析模式。")
        self.settings = settings
        self._last_usage: LLMUsage | None = None
        if sdk_client is None:
            try:
                from openai import OpenAI
            except ImportError as exc:
                raise LLMClientError(
                    "未安装 OpenAI SDK，无法启用 AI 分析模式。"
                ) from exc
            sdk_client = OpenAI(
                api_key=settings.openai_api_key,
                timeout=settings.openai_timeout_seconds,
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
        self._last_usage = None
        try:
            response = self.client.responses.parse(
                model=self.settings.openai_model,
                instructions=PROMPT_PATH.read_text(encoding="utf-8"),
                input=jd_text,
                text_format=JobAnalysis,
                max_output_tokens=1500,
            )
            usage = getattr(response, "usage", None)
            if usage is not None:
                self._last_usage = LLMUsage(
                    input_tokens=coerce_token_count(getattr(usage, "input_tokens", 0)),
                    output_tokens=coerce_token_count(
                        getattr(usage, "output_tokens", 0)
                    ),
                )
            result = response.output_parsed
            if result is None:
                raise ValueError("empty structured output")
            return result.model_copy(update={"source": "ai"})
        except LLMClientError:
            raise
        except Exception as exc:
            raise LLMClientError(
                "大模型服务暂时不可用，请稍后重试或切换到本地规则模式。"
            ) from exc
