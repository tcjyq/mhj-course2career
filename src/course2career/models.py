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


class DegreeLevel(StrEnum):
    HIGH_SCHOOL = "高中及以下"
    ASSOCIATE = "专科"
    BACHELOR = "本科"
    MASTER = "硕士"
    DOCTORATE = "博士"


class InstitutionTier(StrEnum):
    TOP_985 = "985或同层次顶尖高校"
    DOUBLE_FIRST_CLASS = "211或双一流"
    INDUSTRY_RECOGNIZED = "行业特色较强高校"
    STRONG_PUBLIC_UNDERGRADUATE = "较强公办本科"
    PUBLIC_UNDERGRADUATE = "普通公办本科"
    PRIVATE_UNDERGRADUATE = "民办本科或独立学院"
    TOP_VOCATIONAL = "高水平职业院校"
    VOCATIONAL = "普通高职专科"
    OVERSEAS = "海外院校"
    OTHER = "其他"


class EducationProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    degree: DegreeLevel
    institution_tier: InstitutionTier
    major: str = Field(min_length=1)
    academic_percentile: float | None = Field(default=None, ge=0, le=100)
    core_course_average: float | None = Field(default=None, ge=0, le=100)


class ProjectExperience(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    name: str = Field(min_length=1)
    skills: list[str] = Field(default_factory=list)
    relevance: float = Field(ge=0, le=100)
    completeness: float = Field(ge=0, le=100)
    technical_depth: float = Field(ge=0, le=100)
    ownership: float = Field(ge=0, le=100)
    verifiability: float = Field(ge=0, le=100)
    iteration: float = Field(ge=0, le=100)


class InternshipExperience(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    name: str = Field(min_length=1)
    company: str = Field(min_length=1)
    skills: list[str] = Field(default_factory=list)
    relevance: float = Field(ge=0, le=100)
    work_depth: float = Field(ge=0, le=100)
    outcomes: float = Field(ge=0, le=100)
    employer_signal: float = Field(ge=0, le=100)
    duration_months: float = Field(ge=0, le=60)


class PotentialProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    learning_distance: float = Field(ge=0, le=100)
    growth_trajectory: float = Field(ge=0, le=100)
    job_readiness: float = Field(ge=0, le=100)
    motivation: float = Field(ge=0, le=100)
    city_opportunity: float = Field(ge=0, le=100)


class CandidateProfile(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    education: EducationProfile | None = None
    projects: list[ProjectExperience] | None = None
    internships: list[InternshipExperience] | None = None
    potential: PotentialProfile | None = None
    graduation_year: int | None = Field(default=None, ge=2000, le=2100)
    available_days_per_week: int | None = Field(default=None, ge=0, le=7)
    available_months: float | None = Field(default=None, ge=0, le=60)
    preferred_cities: list[str] | None = None


class JobRequirements(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    minimum_degree: DegreeLevel | None = None
    required_graduation_years: list[int] | None = None
    required_major_keywords: list[str] | None = None
    minimum_days_per_week: int | None = Field(default=None, ge=0, le=7)
    minimum_months: float | None = Field(default=None, ge=0, le=60)
    work_city: str | None = None


class EligibilityStatus(StrEnum):
    PASS = "满足"
    CONDITIONAL = "部分满足或待确认"
    FAIL = "存在硬性门槛"


class EligibilityCheck(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    label: str = Field(min_length=1)
    status: EligibilityStatus
    reason: str = Field(min_length=1)


class EligibilityResult(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    status: EligibilityStatus
    checks: list[EligibilityCheck] = Field(default_factory=list)


class DimensionScores(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    technical: float = Field(ge=0, le=100)
    education: float = Field(ge=0, le=100)
    project: float = Field(ge=0, le=100)
    internship: float = Field(ge=0, le=100)
    potential: float = Field(ge=0, le=100)


class ScoreContribution(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    label: str = Field(min_length=1)
    dimension: Literal["technical", "education", "project", "internship", "potential"]
    source_type: str = Field(min_length=1)
    points: float
    reason: str = Field(min_length=1)
    evidence: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)
    actionable: bool = False
    improvement: str | None = None


class LearningModule(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    priority: int = Field(ge=1, le=8)
    name: str = Field(min_length=1)
    related_gaps: list[str] = Field(min_length=1)
    objective: str = Field(min_length=1)
    evidence_goal: str = Field(min_length=1)


class AdaptabilityReport(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    scoring_version: Literal["2.1"] = "2.1"
    job_title: str | None = None
    overall_score: float = Field(ge=0, le=100)
    eligibility: EligibilityResult
    dimension_scores: DimensionScores
    contributions: list[ScoreContribution] = Field(default_factory=list)
    data_completeness: float = Field(ge=0, le=100)
    confidence: Literal["较高", "中等", "初步评估", "信息不足"]
    matches: list[SkillMatch] = Field(default_factory=list)
    strengths: list[str] = Field(default_factory=list)
    gaps: list[str] = Field(default_factory=list)
    learning_modules: list[LearningModule] = Field(default_factory=list)
    limitations: list[str] = Field(default_factory=list)
