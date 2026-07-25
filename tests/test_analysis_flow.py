from course2career.analysis_service import analyze_courses_for_job
from course2career.jd_analyzer import analyze_job_description
from course2career.models import Course, SkillMatchStatus


def test_analysis_service_runs_complete_local_flow() -> None:
    courses = [
        Course(
            name="Python 程序设计",
            credit=3,
            grade=92,
            category="专业必修",
            self_assessment=5,
        ),
        Course(
            name="数据库原理",
            credit=3,
            grade=88,
            category="专业必修",
            self_assessment=4,
        ),
    ]
    job = analyze_job_description(
        "数据分析实习生\n核心要求：熟练掌握 Python 和 SQL。Power BI 项目经验加分。"
    )

    report = analyze_courses_for_job(courses, job)

    assert report.job_title == "数据分析实习生"
    assert 0 < report.overall_score < 100
    assert "Python" in report.strengths
    assert "Power BI" in report.gaps
    assert any(step.skill_name == "Power BI" for step in report.learning_path)
    assert any(match.status == SkillMatchStatus.STRONG for match in report.matches)
    assert report.limitations
