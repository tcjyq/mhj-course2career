import csv
from io import StringIO

from course2career.models import AdaptabilityReport, AnalysisReport


def export_adaptability_markdown(report: AdaptabilityReport) -> str:
    """导出包含资格、五维评分和解释账本的 v2.1 报告。"""

    title = report.job_title or "未命名岗位"
    lines = [
        "# Course2Career 岗位适配度报告",
        "",
        f"- 目标岗位：{title}",
        f"- 岗位适配度：{report.overall_score:.1f}/100",
        f"- 硬门槛状态：{report.eligibility.status.value}",
        f"- 数据完整度：{report.data_completeness:.0f}%",
        f"- 结果可信度：{report.confidence}",
        f"- 评分版本：Career Adaptability Model v{report.scoring_version}",
        "",
        "> 岗位适配度用于比较当前证据与岗位要求，不代表录用概率。",
        "",
        "## 五维评分",
        "",
        "| 维度 | 得分 |",
        "| --- | ---: |",
        f"| 技术技能匹配 | {report.dimension_scores.technical:.1f} |",
        f"| 教育与学术背景 | {report.dimension_scores.education:.1f} |",
        f"| 项目实践能力 | {report.dimension_scores.project:.1f} |",
        f"| 实习实践经验 | {report.dimension_scores.internship:.1f} |",
        f"| 学习潜力与就业条件 | {report.dimension_scores.potential:.1f} |",
        "",
        "## 为什么是这个分数",
        "",
        "| 证据或缺口 | 分数影响 | 原因 |",
        "| --- | ---: | --- |",
        "| 大学生岗位适配度解释基准 | 50.0 | 中性解释基准 |",
    ]
    for item in sorted(
        report.contributions, key=lambda value: value.points, reverse=True
    ):
        sign = "+" if item.points >= 0 else ""
        lines.append(
            f"| {_escape_markdown(item.label)} | {sign}{item.points:.1f} | "
            f"{_escape_markdown(item.reason)} |"
        )

    lines.extend(["", "## 岗位硬门槛", ""])
    if report.eligibility.checks:
        for check in report.eligibility.checks:
            lines.append(f"- {check.label}：{check.status.value}。{check.reason}")
    else:
        lines.append("- 当前JD未设置可结构化核验的硬门槛。")

    lines.extend(["", "## 能力建设路线", ""])
    for module in report.learning_modules:
        lines.extend(
            [
                f"### {module.priority}. {module.name}",
                "",
                f"- 对应缺口：{'、'.join(module.related_gaps)}",
                f"- 目标：{module.objective}",
                f"- 证明成果：{module.evidence_goal}",
                "",
            ]
        )

    lines.extend(["## 使用限制", ""])
    lines.extend(f"- {limitation}" for limitation in report.limitations)
    return "\n".join(lines).rstrip() + "\n"


def _escape_markdown(value: str) -> str:
    return value.replace("|", r"\|").replace("\n", " ")


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


def export_skill_matches_csv(
    report: AnalysisReport | AdaptabilityReport,
) -> bytes:
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
