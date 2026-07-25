import json
from pathlib import Path
from typing import Any

from course2career.models import (
    LearningStep,
    SkillImportance,
    SkillMatch,
    SkillMatchStatus,
)

RESOURCES_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "learning_resources.json"
)
IMPORTANCE_ORDER = {
    SkillImportance.CORE: 0,
    SkillImportance.PREFERRED: 1,
    SkillImportance.BONUS: 2,
}


def load_learning_resources(path: Path | None = None) -> dict[str, dict[str, Any]]:
    with (path or RESOURCES_PATH).open(encoding="utf-8") as file:
        return dict(json.load(file))


def build_learning_path(
    matches: list[SkillMatch],
    resources: dict[str, dict[str, Any]] | None = None,
) -> list[LearningStep]:
    """按岗位重要程度和当前差距生成确定性的学习路线。"""

    resource_map = resources if resources is not None else load_learning_resources()
    candidates = [match for match in matches if match.status != SkillMatchStatus.STRONG]
    candidates.sort(
        key=lambda match: (IMPORTANCE_ORDER[match.importance], match.support_score)
    )
    steps: list[LearningStep] = []
    for priority, match in enumerate(candidates, start=1):
        resource = resource_map.get(
            match.skill_name, _generic_resource(match.skill_name)
        )
        steps.append(
            LearningStep(
                priority=priority,
                skill_name=match.skill_name,
                objective=str(resource["objective"]),
                action=str(resource["action"]),
                project=str(resource["project"]),
                completion_criteria=str(resource["completion_criteria"]),
                estimated_hours=float(resource["estimated_hours"]),
            )
        )
    return steps


def _generic_resource(skill_name: str) -> dict[str, str | float]:
    return {
        "objective": f"掌握 {skill_name} 的岗位常用基础能力",
        "action": f"梳理 {skill_name} 的核心概念，并完成循序渐进的练习",
        "project": f"完成一个可展示的 {skill_name} 小项目",
        "completion_criteria": "项目有清晰说明、可复现步骤和自测记录",
        "estimated_hours": 16,
    }
