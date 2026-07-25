from course2career.adaptability import assess_job_adaptability
from course2career.models import (
    AnalysisReport,
    CandidateProfile,
    Course,
    DegreeLevel,
    EducationProfile,
    InstitutionTier,
    JobAnalysis,
    JobRequirements,
    JobSkill,
    LearningStep,
    SkillImportance,
    SkillMatch,
    SkillMatchStatus,
)
from course2career.report_exporter import (
    export_adaptability_markdown,
    export_markdown,
    export_skill_matches_csv,
)


def _report() -> AnalysisReport:
    return AnalysisReport(
        job_title="数据分析师",
        overall_score=68.5,
        matches=[
            SkillMatch(
                skill_name="SQL",
                importance=SkillImportance.CORE,
                support_score=82,
                status=SkillMatchStatus.STRONG,
            )
        ],
        strengths=["SQL"],
        gaps=[],
        learning_path=[
            LearningStep(
                priority=1,
                skill_name="Power BI",
                objective="掌握基础",
                action="完成练习",
                project="制作看板",
                completion_criteria="可复现",
                estimated_hours=12,
            )
        ],
        limitations=["结果用于学习规划，不代表招聘结论。"],
    )


def test_export_markdown_contains_summary_and_learning_path() -> None:
    content = export_markdown(_report())

    assert "# Course2Career 分析报告" in content
    assert "68.5" in content
    assert "Power BI" in content
    assert "结果用于学习规划" in content


def test_export_csv_is_excel_friendly_utf8() -> None:
    content = export_skill_matches_csv(_report())

    assert content.startswith(b"\xef\xbb\xbf")
    decoded = content.decode("utf-8-sig")
    assert "技能,重要程度,支撑分,匹配状态,支撑课程" in decoded
    assert "SQL,核心,82.0,较强支撑" in decoded


def test_export_adaptability_markdown_explains_score_and_not_probability() -> None:
    result = assess_job_adaptability(
        courses=[
            Course(
                name="Python程序设计",
                credit=3,
                grade=88,
                category="专业必修",
                self_assessment=4,
            )
        ],
        job_analysis=JobAnalysis(
            job_title="AI应用开发实习生",
            source="manual",
            skills=[
                JobSkill(
                    name="Python",
                    normalized_name="Python",
                    category="编程",
                    importance=SkillImportance.CORE,
                    evidence_text="熟悉Python",
                )
            ],
        ),
        profile=CandidateProfile(
            education=EducationProfile(
                degree=DegreeLevel.BACHELOR,
                institution_tier=InstitutionTier.PUBLIC_UNDERGRADUATE,
                major="信息管理与信息系统",
                core_course_average=82,
            )
        ),
        requirements=JobRequirements(minimum_degree=DegreeLevel.BACHELOR),
    )

    content = export_adaptability_markdown(result)

    assert "岗位适配度" in content
    assert "为什么是这个分数" in content
    assert "不代表录用概率" in content
    assert "50.0" in content
