import pytest

from course2career.jd_analyzer import JDAnalysisError, analyze_job_description
from course2career.models import JobAnalysis, JobSkill, SkillImportance


def test_rule_analyzer_extracts_skills_evidence_and_importance() -> None:
    jd = """
    数据分析实习生
    核心要求：熟练掌握 Python 和 SQL，能够完成数据清洗和查询。
    有 Power BI 项目经验者加分，并具备良好的沟通能力。
    """

    result = analyze_job_description(jd)

    skills = {skill.name: skill for skill in result.skills}
    assert result.source == "rules"
    assert result.job_title == "数据分析实习生"
    assert skills["Python"].importance == SkillImportance.CORE
    assert skills["SQL"].evidence_text.startswith("核心要求")
    assert skills["Power BI"].importance == SkillImportance.BONUS
    assert skills["沟通协作"].category == "通用能力"


def test_rule_analyzer_rejects_too_short_or_unrecognized_jd() -> None:
    with pytest.raises(JDAnalysisError, match="至少"):
        analyze_job_description("会 SQL")

    with pytest.raises(JDAnalysisError, match="未识别"):
        analyze_job_description("负责日常运营工作，认真完成负责人安排的各项业务任务。")


def test_analyzer_uses_injected_ai_client() -> None:
    expected = JobAnalysis(
        job_title="业务分析师",
        source="ai",
        skills=[
            JobSkill(
                name="需求分析",
                normalized_name="需求分析",
                category="业务能力",
                importance=SkillImportance.CORE,
                evidence_text="负责业务需求分析",
            )
        ],
    )

    class FakeClient:
        def extract_job_skills(self, jd_text: str) -> JobAnalysis:
            assert "业务分析" in jd_text
            return expected

    assert (
        analyze_job_description(
            "业务分析岗位，负责业务需求分析与流程梳理。", FakeClient()
        )
        == expected
    )
