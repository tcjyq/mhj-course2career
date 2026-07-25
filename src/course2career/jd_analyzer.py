import re

from course2career.llm_provider import LLMProvider
from course2career.models import JobAnalysis, JobSkill, SkillImportance
from course2career.skill_normalizer import find_skills_in_text

MIN_JD_LENGTH = 20
MAX_JD_LENGTH = 12_000

SKILL_CATEGORIES = {
    "Python": "技术工具",
    "SQL": "数据能力",
    "Excel": "技术工具",
    "Power BI": "技术工具",
    "Tableau": "技术工具",
    "pandas": "技术工具",
    "数据分析": "数据能力",
    "统计分析": "数据能力",
    "数据可视化": "数据能力",
    "数据库设计": "技术能力",
    "数据建模": "数据能力",
    "需求分析": "业务能力",
    "业务流程分析": "业务能力",
    "信息系统": "业务能力",
    "ERP": "业务能力",
    "项目管理": "通用能力",
    "沟通协作": "通用能力",
    "Git": "工程能力",
    "机器学习": "技术能力",
    "Java": "技术能力",
}


class JDAnalysisError(ValueError):
    """岗位描述无法形成可用分析结果。"""


def analyze_job_description(
    jd_text: str, client: LLMProvider | None = None
) -> JobAnalysis:
    """校验 JD，并使用指定客户端或本地规则提取技能。"""

    cleaned_text = jd_text.strip()
    if len(cleaned_text) < MIN_JD_LENGTH:
        raise JDAnalysisError(f"岗位描述至少需要 {MIN_JD_LENGTH} 个字符。")
    if len(cleaned_text) > MAX_JD_LENGTH:
        raise JDAnalysisError(f"岗位描述不能超过 {MAX_JD_LENGTH} 个字符。")
    if client is not None:
        result = client.extract_job_skills(cleaned_text)
        if not result.skills:
            raise JDAnalysisError("未识别到可用于匹配的岗位技能。")
        return result
    return _analyze_with_rules(cleaned_text)


def _analyze_with_rules(jd_text: str) -> JobAnalysis:
    segments = [
        segment.strip(" ：:，,。；;\t")
        for segment in re.split(r"[。；;\n]+", jd_text)
        if segment.strip()
    ]
    found_skills: dict[str, JobSkill] = {}
    for segment in segments:
        importance = _infer_importance(segment)
        for skill_name in find_skills_in_text(segment):
            candidate = JobSkill(
                name=skill_name,
                normalized_name=skill_name,
                category=SKILL_CATEGORIES.get(skill_name, "其他能力"),
                importance=importance,
                evidence_text=segment,
            )
            current = found_skills.get(skill_name)
            if current is None or _importance_rank(importance) > _importance_rank(
                current.importance
            ):
                found_skills[skill_name] = candidate

    if not found_skills:
        raise JDAnalysisError("未识别到可用于匹配的岗位技能，请补充岗位要求。")
    first_line = next(line.strip() for line in jd_text.splitlines() if line.strip())
    job_title = first_line if len(first_line) <= 40 else None
    return JobAnalysis(
        job_title=job_title, skills=list(found_skills.values()), source="rules"
    )


def _infer_importance(segment: str) -> SkillImportance:
    lowered = segment.casefold()
    if any(word in lowered for word in ("加分", "preferred", "plus", "优先考虑")):
        return SkillImportance.BONUS
    if any(
        word in lowered
        for word in ("核心", "必须", "必备", "熟练", "精通", "required", "must")
    ):
        return SkillImportance.CORE
    return SkillImportance.PREFERRED


def _importance_rank(importance: SkillImportance) -> int:
    return {
        SkillImportance.BONUS: 1,
        SkillImportance.PREFERRED: 2,
        SkillImportance.CORE: 3,
    }[importance]
