import pytest

from course2career.models import (
    CourseSkillEvidence,
    JobSkill,
    SkillImportance,
    SkillMatchStatus,
)
from course2career.scoring import build_skill_matches, calculate_overall_score


def _job_skill(name: str, importance: SkillImportance) -> JobSkill:
    return JobSkill(
        name=name,
        normalized_name=name,
        category="数据能力",
        importance=importance,
        evidence_text=f"要求掌握 {name}",
    )


def test_build_skill_matches_assigns_status_from_best_evidence() -> None:
    skills = [
        _job_skill("SQL", SkillImportance.CORE),
        _job_skill("Excel", SkillImportance.PREFERRED),
        _job_skill("Power BI", SkillImportance.BONUS),
    ]
    evidences = [
        CourseSkillEvidence(
            course_name="数据库原理",
            skill_name="SQL",
            mapping_strength=0.9,
            course_score=88,
            evidence_score=83.9,
            explanation="课程名称命中数据库",
        ),
        CourseSkillEvidence(
            course_name="办公自动化",
            skill_name="Excel",
            mapping_strength=0.5,
            course_score=70,
            evidence_score=55,
            explanation="课程名称命中办公自动化",
        ),
    ]

    matches = build_skill_matches(skills, evidences)

    assert [match.status for match in matches] == [
        SkillMatchStatus.STRONG,
        SkillMatchStatus.PARTIAL,
        SkillMatchStatus.GAP,
    ]
    assert matches[0].support_score == 83.9
    assert matches[2].evidences == []


def test_calculate_overall_score_uses_importance_weights() -> None:
    skills = [
        _job_skill("SQL", SkillImportance.CORE),
        _job_skill("Power BI", SkillImportance.BONUS),
    ]
    evidences = [
        CourseSkillEvidence(
            course_name="数据库原理",
            skill_name="SQL",
            mapping_strength=0.9,
            course_score=88,
            evidence_score=80,
            explanation="课程名称命中数据库",
        )
    ]

    score = calculate_overall_score(build_skill_matches(skills, evidences))

    assert score == pytest.approx(57.1, abs=0.1)
