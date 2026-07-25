from course2career.learning_path import build_learning_path
from course2career.models import SkillImportance, SkillMatch, SkillMatchStatus


def test_learning_path_prioritizes_core_gaps_and_skips_strong_skills() -> None:
    matches = [
        SkillMatch(
            skill_name="Excel",
            importance=SkillImportance.PREFERRED,
            support_score=75,
            status=SkillMatchStatus.STRONG,
        ),
        SkillMatch(
            skill_name="Power BI",
            importance=SkillImportance.BONUS,
            support_score=0,
            status=SkillMatchStatus.GAP,
        ),
        SkillMatch(
            skill_name="SQL",
            importance=SkillImportance.CORE,
            support_score=35,
            status=SkillMatchStatus.GAP,
        ),
    ]

    steps = build_learning_path(matches)

    assert [step.skill_name for step in steps] == ["SQL", "Power BI"]
    assert [step.priority for step in steps] == [1, 2]
    assert steps[0].estimated_hours > 0
    assert steps[1].project
