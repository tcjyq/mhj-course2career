import json
from pathlib import Path
from typing import Any

from course2career.llm_client import LLMClientError
from course2career.llm_provider import LLMUsage, ProviderName, coerce_token_count
from course2career.models import JobAnalysis

PROMPT_PATH = Path(__file__).resolve().parents[2] / "prompts" / "extract_jd_skills.txt"
DEEPSEEK_BASE_URL = "https://api.deepseek.com"
DEEPSEEK_MODELS = frozenset({"deepseek-v4-flash", "deepseek-v4-pro"})


class ProviderError(LLMClientError):
    """模型供应商配置或调用失败。"""


class DeepSeekProvider:
    """通过DeepSeek的OpenAI兼容Chat Completions接口提取岗位技能。"""

    def __init__(
        self,
        *,
        api_key: str,
        model: str = "deepseek-v4-flash",
        timeout_seconds: float = 30,
        sdk_client: Any | None = None,
    ) -> None:
        if not api_key:
            raise ProviderError("未配置 DeepSeek API Key。")
        if model not in DEEPSEEK_MODELS:
            raise ProviderError("不支持的 DeepSeek 模型。")
        self.model = model
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
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": instructions},
                    {"role": "user", "content": jd_text},
                ],
                response_format={"type": "json_object"},
                max_tokens=1500,
                stream=False,
                extra_body={"thinking": {"type": "disabled"}},
            )
            usage = getattr(response, "usage", None)
            if usage is not None:
                self._last_usage = LLMUsage(
                    input_tokens=coerce_token_count(getattr(usage, "prompt_tokens", 0)),
                    output_tokens=coerce_token_count(
                        getattr(usage, "completion_tokens", 0)
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
