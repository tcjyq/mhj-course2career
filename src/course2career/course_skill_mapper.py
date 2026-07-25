import json
from pathlib import Path
from typing import Any

from course2career.models import Course, CourseSkillEvidence, JobSkill

RULES_PATH = Path(__file__).resolve().parents[2] / "data" / "course_skill_map.json"


def load_course_skill_rules(path: Path | None = None) -> list[dict[str, Any]]:
    with (path or RULES_PATH).open(encoding="utf-8") as file:
        return list(json.load(file))


def map_courses_to_skills(
    courses: list[Course],
    target_skills: list[JobSkill] | None,
    rules: list[dict[str, Any]] | None = None,
) -> list[CourseSkillEvidence]:
    """通过可审计的课程关键词规则生成技能支撑证据。"""

    course_rules = rules if rules is not None else load_course_skill_rules()
    targets = (
        {skill.normalized_name for skill in target_skills}
        if target_skills is not None
        else None
    )
    best_matches: dict[tuple[str, str], CourseSkillEvidence] = {}

    for course in courses:
        lowered_name = course.name.casefold()
        for rule in course_rules:
            matched_keywords = [
                str(keyword)
                for keyword in rule["course_keywords"]
                if str(keyword).casefold() in lowered_name
            ]
            if not matched_keywords:
                continue
            for skill_name, strength_value in rule["skills"].items():
                if targets is not None and skill_name not in targets:
                    continue
                strength = float(strength_value)
                evidence = CourseSkillEvidence(
                    course_name=course.name,
                    skill_name=skill_name,
                    mapping_strength=strength,
                    course_score=course.grade,
                    evidence_score=_calculate_evidence_score(course, strength),
                    explanation=f"课程名称命中“{matched_keywords[0]}”规则。",
                )
                key = (course.name, skill_name)
                current = best_matches.get(key)
                if current is None or evidence.evidence_score > current.evidence_score:
                    best_matches[key] = evidence
    return list(best_matches.values())


def _calculate_evidence_score(course: Course, mapping_strength: float) -> float:
    score = (
        course.grade * 0.30
        + (course.self_assessment / 5 * 100) * 0.25
        + (mapping_strength * 100) * 0.35
        + min(course.credit / 5, 1) * 100 * 0.10
    )
    return round(score, 1)
