from enum import StrEnum
from typing import Protocol, runtime_checkable

from course2career.models import JobAnalysis


class ProviderName(StrEnum):
    OPENAI = "openai"
    DEEPSEEK = "deepseek"


@runtime_checkable
class LLMProvider(Protocol):
    """岗位技能提取所依赖的供应商无关接口。"""

    @property
    def provider_name(self) -> ProviderName: ...

    @property
    def model_name(self) -> str: ...

    def extract_job_skills(self, jd_text: str) -> JobAnalysis: ...
