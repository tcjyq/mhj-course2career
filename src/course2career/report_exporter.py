import csv
from io import StringIO

from course2career.models import AnalysisReport


def export_markdown(report: AnalysisReport) -> str:
    """将分析报告导出为适合 GitHub 阅读的 Markdown。"""

    title = report.job_title or "未命名岗位"
    lines = [
        "# Course2Career 分析报告",
        "",
        f"- 目标岗位：{title}",
        f"- 综合匹配分：{report.overall_score:.1f}/100",
        "",
        "## 技能匹配",
        "",
        "| 技能 | 重要程度 | 支撑分 | 状态 | 支撑课程 |",
        "| --- | --- | ---: | --- | --- |",
    ]
    for match in report.matches:
        courses = (
            "、".join(evidence.course_name for evidence in match.evidences) or "无"
        )
        lines.append(
            f"| {match.skill_name} | {match.importance.value} | "
            f"{match.support_score:.1f} | {match.status.value} | {courses} |"
        )

    lines.extend(["", "## 推荐学习路线", ""])
    if report.learning_path:
        for step in report.learning_path:
            lines.extend(
                [
                    f"### {step.priority}. {step.skill_name}",
                    "",
                    f"- 目标：{step.objective}",
                    f"- 行动：{step.action}",
                    f"- 实践项目：{step.project}",
                    f"- 完成标准：{step.completion_criteria}",
                    f"- 预计投入：{step.estimated_hours:g} 小时",
                    "",
                ]
            )
    else:
        lines.extend(["当前没有需要优先补齐的技能。", ""])

    lines.extend(["## 使用限制", ""])
    lines.extend(f"- {limitation}" for limitation in report.limitations)
    return "\n".join(lines).rstrip() + "\n"


def export_skill_matches_csv(report: AnalysisReport) -> bytes:
    """导出带 UTF-8 BOM 的技能明细，便于 Excel 直接打开。"""

    output = StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(["技能", "重要程度", "支撑分", "匹配状态", "支撑课程"])
    for match in report.matches:
        courses = "、".join(evidence.course_name for evidence in match.evidences)
        writer.writerow(
            [
                match.skill_name,
                match.importance.value,
                f"{match.support_score:.1f}",
                match.status.value,
                courses,
            ]
        )
    return output.getvalue().encode("utf-8-sig")
