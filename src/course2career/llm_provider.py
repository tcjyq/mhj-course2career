from enum import StrEnum
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from course2career.models import JobAnalysis

if TYPE_CHECKING:
    from course2career.provider_runtime import ModelTrace, ProviderCallResult


class ProviderName(StrEnum):
    OPENAI = "openai"
    DEEPSEEK = "deepseek"
    BAILIAN = "bailian"
    OPENROUTER = "openrouter"
    SILICONFLOW = "siliconflow"
    MOONSHOT = "moonshot"
    ZHIPU = "zhipu"
    MINIMAX = "minimax"
    GEMINI = "gemini"
    ANTHROPIC = "anthropic"


class LLMUsage(BaseModel):
    """真实 Token 用量；model 是账目展示标签，不是返回模型的认证证据。"""

    model_config = ConfigDict(frozen=True)

    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)
    model: str | None = None
    system_fingerprint: str | None = None


def coerce_token_count(value: object) -> int:
    if not isinstance(value, int | float | str):
        return 0
    try:
        return max(int(value), 0)
    except (TypeError, ValueError):
        return 0


@runtime_checkable
class LLMProvider(Protocol):
    """岗位技能提取所依赖的供应商无关接口。"""

    @property
    def provider_name(self) -> ProviderName: ...

    @property
    def model_name(self) -> str: ...

    @property
    def last_usage(self) -> LLMUsage | None: ...

    @property
    def last_trace(self) -> "ModelTrace": ...

    @property
    def last_result(self) -> "ProviderCallResult | None": ...

    def extract_job_skills(self, jd_text: str) -> JobAnalysis: ...
