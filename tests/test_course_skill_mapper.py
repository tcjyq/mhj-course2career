import pytest

from course2career.course_skill_mapper import map_courses_to_skills
from course2career.models import Course, JobSkill, SkillImportance


def test_map_courses_to_target_skills_builds_explainable_evidence() -> None:
    courses = [
        Course(
            name="数据库原理",
            credit=3,
            grade=88,
            category="专业必修",
            self_assessment=4,
        )
    ]
    target_skills = [
        JobSkill(
            name="SQL",
            normalized_name="SQL",
            category="数据能力",
            importance=SkillImportance.CORE,
            evidence_text="熟练使用 SQL",
        ),
        JobSkill(
            name="Power BI",
            normalized_name="Power BI",
            category="技术工具",
            importance=SkillImportance.BONUS,
            evidence_text="Power BI 加分",
        ),
    ]

    evidences = map_courses_to_skills(courses, target_skills)

    assert len(evidences) == 1
    assert evidences[0].course_name == "数据库原理"
    assert evidences[0].skill_name == "SQL"
    assert evidences[0].mapping_strength == 0.9
    assert evidences[0].evidence_score == pytest.approx(83.9)
    assert "课程名称命中" in evidences[0].explanation
