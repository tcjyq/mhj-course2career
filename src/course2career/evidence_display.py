"""从既有证据生成展示说明，不参与评分。"""

from course2career.models import EligibilityResult, SkillMatch

EVIDENCE_NOTICE = (
    "直接材料仅表示输入明确提及技能，不代表外部核验或熟练掌握。"
    "课程名称与成绩、项目和实习均由用户提供；自述及人工确认不等于独立验证。"
    "间接或迁移依据只能支持相关基础；材料未体现不等于不会。"
)


def eligibility_label(result: EligibilityResult) -> str:
    return result.status.value if result.checks else "未设置／待确认"


def skill_sources(match: SkillMatch) -> list[str]:
    if match.sources is not None:
        return match.sources or ["材料未体现：未找到课程、项目、实习或迁移依据"]
    # 旧快照未存完整sources，不能将缺少字段解释为没有证据。
    return [
        f"历史课程材料（类型待确认）：{item.course_name}；{item.explanation}"
        for item in match.evidences
    ] + ["历史快照未记录完整来源类型，请结合原始账本核对"]
