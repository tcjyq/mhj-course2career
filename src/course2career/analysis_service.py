from course2career.course_skill_mapper import map_courses_to_skills
from course2career.learning_path import build_learning_path
from course2career.models import (
    AnalysisReport,
    Course,
    JobAnalysis,
    SkillMatchStatus,
)
from course2career.scoring import build_skill_matches, calculate_overall_score


def analyze_courses_for_job(
    courses: list[Course], job_analysis: JobAnalysis
) -> AnalysisReport:
    """串联课程映射、评分和学习路线，形成完整分析报告。"""

    evidences = map_courses_to_skills(courses, job_analysis.skills)
    matches = build_skill_matches(job_analysis.skills, evidences)
    return AnalysisReport(
        job_title=job_analysis.job_title,
        overall_score=calculate_overall_score(matches),
        matches=matches,
        strengths=[
            match.skill_name
            for match in matches
            if match.status == SkillMatchStatus.STRONG
        ],
        gaps=[
            match.skill_name
            for match in matches
            if match.status == SkillMatchStatus.GAP
        ],
        learning_path=build_learning_path(matches),
        limitations=[
            "课程与技能关系来自内置规则，无法替代课程大纲或项目作品等真实证据。",
            "匹配分用于学习规划，不代表招聘录用概率或个人能力的最终评价。",
            "岗位技能提取可能遗漏上下文，请在分析前人工确认技能清单。",
        ],
    )
