from io import BytesIO
from zipfile import ZipFile

import pytest
from pydantic import ValidationError

from course2career.adaptability import assess_job_adaptability
from course2career.course_parser import read_course_excel
from course2career.course_skill_mapper import map_courses_to_skills
from course2career.demo_cases import demo_inputs, export_demo_bundle, load_demo_cases
from course2career.evidence_display import eligibility_label, skill_sources
from course2career.jd_analyzer import analyze_job_description, evidence_status
from course2career.models import (
    AdaptabilityReport,
    CandidateProfile,
    Course,
    EducationProfile,
    JobAnalysis,
    JobRequirements,
    JobSkill,
    PotentialProfile,
    ProjectExperience,
)
from course2career.report_exporter import export_adaptability_markdown


def course(name):
    return Course(name=name, credit=3, grade=88, category="合成", self_assessment=4)


def skill(name, quote=None, importance="核心"):
    return JobSkill(
        name=name,
        normalized_name=name,
        category="合成",
        importance=importance,
        evidence_text=quote or f"要求{name}",
    )


@pytest.mark.parametrize(
    "name,expected",
    [
        ("Java程序设计", {"Java"}),
        ("C语言程序设计", set()),
        ("Python程序设计", {"Python"}),
        ("通用编程", set()),
        ("数据可视化", {"数据可视化"}),
        ("Power BI课程", {"Power BI", "数据可视化"}),
        ("Python与pandas", {"Python", "pandas"}),
        ("Tableau课程", {"Tableau", "数据可视化"}),
        ("JavaScript程序设计", set()),
    ],
)
def test_course_names_do_not_invent_specific_tools(name, expected):
    actual = map_courses_to_skills([course(name)], None)
    assert {item.skill_name for item in actual} == expected


def test_other_explicit_evidence_survives_and_scores_stay_identical():
    mapped = map_courses_to_skills(
        [course("Java程序设计"), course("Python实践")], [skill("Python")]
    )
    assert len(mapped) == 1
    assert mapped[0].course_name == "Python实践"
    assert mapped[0].evidence_score == 83.9
    sql = map_courses_to_skills([course("数据库原理")], [skill("SQL")])
    assert sql[0].evidence_score == 83.9


@pytest.mark.parametrize(
    "quote,jd,expected",
    [
        ("要求SQL", "岗位要求SQL", "原文命中；技能名称／别名明确提及"),
        ("要求 SQL", "岗位要求\n  SQL", "空白规范化命中；技能名称／别名明确提及"),
        ("熟悉SQL", "岗位要求SQL", "待确认：引用无法在当前JD定位"),
        ("要求MySQL", "岗位要求MySQL", "原文命中；技能名称／别名明确提及"),
        ("数据库查询", "要求数据库查询", "原文命中；技能为推断，待确认关联"),
        ("要求 SQL", "要求 S Q L", "待确认：引用无法在当前JD定位"),
    ],
)
def test_quotes_and_skill_interpretation_are_separate(quote, jd, expected):
    assert evidence_status(skill("SQL", quote), jd) == expected


def test_empty_quote_is_rejected_and_manual_correction_is_rechecked():
    with pytest.raises(ValidationError):
        skill("SQL").model_validate({**skill("SQL").model_dump(), "evidence_text": " "})
    bad = skill("SQL", "虚构要求")
    assert "待确认" in evidence_status(bad, "核心要求SQL")
    corrected = bad.model_copy(update={"evidence_text": "要求SQL"})
    assert evidence_status(corrected, "核心要求SQL").startswith("原文命中")


def test_fixed_provider_output_is_checked_without_a_second_call():
    class Fake:
        calls = 0

        def extract_job_skills(self, jd_text):
            self.calls += 1
            return JobAnalysis(source="ai", skills=[skill("SQL", "虚构引用")])

    client = Fake()
    jd = "数据分析实习生，核心要求SQL，完成数据核对和查询。"
    result = analyze_job_description(jd, client)
    assert "待确认" in evidence_status(result.skills[0], jd)
    assert client.calls == 1


def test_completeness_is_not_experience_quality_and_empty_gate_is_not_pass():
    job = JobAnalysis(skills=[skill("SQL")])
    unknown = assess_job_adaptability(
        [course("SQL")], job, CandidateProfile(), JobRequirements()
    )
    complete_profile = CandidateProfile(
        education=EducationProfile(
            degree="本科", institution_tier="普通公办本科", major="信息管理与信息系统"
        ),
        projects=[],
        internships=[],
        graduation_year=2027,
        potential=PotentialProfile(
            learning_distance=50,
            growth_trajectory=50,
            job_readiness=50,
            motivation=50,
            city_opportunity=50,
        ),
    )
    complete = assess_job_adaptability(
        [course("SQL")],
        job,
        complete_profile,
        JobRequirements(required_graduation_years=[2027]),
    )
    assert unknown.dimension_scores.project == 50
    assert complete.dimension_scores.project < 50
    assert complete.dimension_scores.internship < 50
    assert complete.data_completeness == 100
    assert eligibility_label(unknown.eligibility) == "未设置／待确认"
    assert eligibility_label(complete.eligibility) == "满足"
    text = export_adaptability_markdown(unknown)
    assert "未设置／待确认" in text
    assert "资料完整度等级" in text


def test_learning_priority_and_unknown_skill_template_are_deterministic():
    report = assess_job_adaptability(
        [],
        JobAnalysis(
            skills=[
                skill("Docker", importance="加分"),
                skill("SQL"),
                skill("未知技能"),
            ]
        ),
        CandidateProfile(),
        JobRequirements(),
    )
    assert [m.related_gaps for m in report.learning_modules] == [
        ["SQL"],
        ["未知技能"],
        ["Docker"],
    ]
    assert "关联" in report.learning_modules[0].task
    unknown = report.learning_modules[1]
    assert "待确认" in unknown.completion_criteria
    assert all(word not in unknown.task for word in ("Agent", "RAG", "Docker"))


def test_all_sources_and_missing_material_are_explained_without_score_drift():
    projects = [
        ProjectExperience(
            name=f"合成项目{i}",
            skills=["Python"],
            relevance=80,
            completeness=80,
            technical_depth=80,
            ownership=80,
            verifiability=80,
            iteration=80,
        )
        for i in range(3)
    ]
    report = assess_job_adaptability(
        [course("Python程序设计")],
        JobAnalysis(skills=[skill("Python"), skill("FastAPI"), skill("SQL")]),
        CandidateProfile(projects=projects),
        JobRequirements(),
    )
    python, fastapi, sql = report.matches
    assert len(python.sources) == 4
    assert "直接材料" in "；".join(python.sources)
    assert "用户自述" in "；".join(python.sources)
    assert python.support_score == 100  # min(83.9 + 80*.2 + 80*.1, 100)
    assert "迁移" in "；".join(fastapi.sources)
    assert "材料未体现" in skill_sources(sql)[0]
    assert sql.support_score == 15
    assert "合成项目2" in export_adaptability_markdown(report)
    assert 50 + sum(item.points for item in report.contributions) == pytest.approx(
        report.overall_score, abs=0.11
    )
    old = report.model_dump()
    for match in old["matches"]:
        match.pop("sources")
    for module in old["learning_modules"]:
        module.pop("task")
        module.pop("completion_criteria")
    restored = AdaptabilityReport.model_validate(old)
    assert "历史快照" in "；".join(skill_sources(restored.matches[2]))
    assert restored.overall_score == report.overall_score
    assert "历史报告未记录" in export_adaptability_markdown(restored)


def test_alias_source_lookup_keeps_user_statement_and_does_not_crash():
    project = ProjectExperience(
        name="合成查询练习",
        skills=["SQL"],
        relevance=80,
        completeness=80,
        technical_depth=80,
        ownership=80,
        verifiability=80,
        iteration=80,
    )
    report = assess_job_adaptability(
        [],
        JobAnalysis(skills=[skill("MySQL")]),
        CandidateProfile(projects=[project]),
        JobRequirements(),
    )
    assert report.matches[0].support_score == 80
    assert "用户自述" in report.contributions[0].evidence[0]


@pytest.mark.parametrize("case", load_demo_cases(), ids=lambda case: case["id"])
def test_synthetic_cases_have_valid_downloads_gates_and_actionable_tasks(case):
    courses, profile, requirements = demo_inputs(case)
    with ZipFile(BytesIO(export_demo_bundle(case))) as bundle:
        imported = read_course_excel(BytesIO(bundle.read("courses.xlsx")))
        assert not imported.errors
        assert imported.courses == courses
        assert bundle.read("jd.txt").decode("utf-8") == case["jd"]
    report = assess_job_adaptability(
        courses, analyze_job_description(case["jd"]), profile, requirements
    )
    assert "合成演示" in export_adaptability_markdown(report)
    if case["id"] == "digital-support":
        assert eligibility_label(report.eligibility) == "部分满足或待确认"
        assert report.data_completeness == 25
        assert any("字段字典" in item.evidence_goal for item in report.learning_modules)
    elif case["id"] == "ai-solutions":
        assert eligibility_label(report.eligibility) == "未设置／待确认"
        assert any("固定响应" in item.task for item in report.learning_modules)
        assert any("迁移" in "；".join(m.sources) for m in report.matches)
    else:
        assert eligibility_label(report.eligibility) == "存在硬性门槛"
        assert report.dimension_scores.technical > 70
        assert report.learning_modules == []
    for module in report.learning_modules:
        assert module.task and module.evidence_goal and module.completion_criteria
        assert all(
            any(m.skill_name == gap and m.support_score < 50 for m in report.matches)
            for gap in module.related_gaps
        )
