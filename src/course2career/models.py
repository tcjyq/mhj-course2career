from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SkillImportance(StrEnum):
    CORE = "核心"
    PREFERRED = "优先"
    BONUS = "加分"


class SkillMatchStatus(StrEnum):
    STRONG = "较强支撑"
    PARTIAL = "有一定基础"
    GAP = "当前缺口"


class Course(BaseModel):
    """一门课程及其可用于能力分析的学习证据。"""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    name: str = Field(min_length=1)
    credit: float = Field(gt=0, le=20)
    grade: float = Field(ge=0, le=100)
    category: str = Field(min_length=1)
    self_assessment: int = Field(ge=1, le=5)


class CourseRowError(BaseModel):
    """课程表中单个字段的校验错误。"""

    model_config = ConfigDict(frozen=True)

    row_number: int = Field(ge=2)
    field: str
    message: str


class CourseImportResult(BaseModel):
    """课程导入结果，保留合法课程和可展示的行级错误。"""

    courses: list[Course] = Field(default_factory=list)
    errors: list[CourseRowError] = Field(default_factory=list)


class JobSkill(BaseModel):
    """岗位描述中可核验的一项技能要求。"""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    name: str = Field(min_length=1)
    normalized_name: str = Field(min_length=1)
    category: str = Field(min_length=1)
    importance: SkillImportance = SkillImportance.PREFERRED
    evidence_text: str = Field(min_length=1)


class JobAnalysis(BaseModel):
    """岗位技能提取结果。"""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    job_title: str | None = None
    skills: list[JobSkill] = Field(default_factory=list)
    source: Literal["ai", "rules", "manual"] = "rules"


class CourseSkillEvidence(BaseModel):
    """一门课程对一项岗位技能的可解释支撑证据。"""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    course_name: str = Field(min_length=1)
    skill_name: str = Field(min_length=1)
    mapping_strength: float = Field(ge=0, le=1)
    course_score: float = Field(ge=0, le=100)
    evidence_score: float = Field(ge=0, le=100)
    explanation: str = Field(min_length=1)


class SkillMatch(BaseModel):
    """单项岗位技能与课程证据的匹配结果。"""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    skill_name: str = Field(min_length=1)
    importance: SkillImportance
    support_score: float = Field(ge=0, le=100)
    status: SkillMatchStatus
    evidences: list[CourseSkillEvidence] = Field(default_factory=list)


class LearningStep(BaseModel):
    """针对技能差距生成的一项可验收学习任务。"""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    priority: int = Field(ge=1)
    skill_name: str = Field(min_length=1)
    objective: str = Field(min_length=1)
    action: str = Field(min_length=1)
    project: str = Field(min_length=1)
    completion_criteria: str = Field(min_length=1)
    estimated_hours: float = Field(gt=0)


class AnalysisReport(BaseModel):
    """一次课程能力与岗位技能匹配的完整结果。"""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    job_title: str | None = None
    overall_score: float = Field(ge=0, le=100)
    matches: list[SkillMatch] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    learning_path: list[LearningStep] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
