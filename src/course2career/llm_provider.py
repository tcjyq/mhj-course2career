from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from course2career.models import JobAnalysis


class ProviderName(StrEnum):
    OPENAI = "openai"
    DEEPSEEK = "deepseek"


class LLMUsage(BaseModel):
    """一次模型调用返回的真实Token用量。"""

    model_config = ConfigDict(frozen=True)

    input_tokens: int = Field(ge=0)
    output_tokens: int = Field(ge=0)


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

    def extract_job_skills(self, jd_text: str) -> JobAnalysis: ...
