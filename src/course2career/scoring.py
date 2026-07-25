from collections import defaultdict

from course2career.models import (
    CourseSkillEvidence,
    JobSkill,
    SkillImportance,
    SkillMatch,
    SkillMatchStatus,
)

IMPORTANCE_WEIGHTS = {
    SkillImportance.CORE: 1.0,
    SkillImportance.PREFERRED: 0.7,
    SkillImportance.BONUS: 0.4,
}


def build_skill_matches(
    job_skills: list[JobSkill], evidences: list[CourseSkillEvidence]
) -> list[SkillMatch]:
    """汇总每项技能的课程证据，以最强证据确定支撑分。"""

    evidence_by_skill: dict[str, list[CourseSkillEvidence]] = defaultdict(list)
    for evidence in evidences:
        evidence_by_skill[evidence.skill_name].append(evidence)

    matches: list[SkillMatch] = []
    for skill in job_skills:
        skill_evidences = sorted(
            evidence_by_skill.get(skill.normalized_name, []),
            key=lambda item: item.evidence_score,
            reverse=True,
        )
        support_score = skill_evidences[0].evidence_score if skill_evidences else 0.0
        matches.append(
            SkillMatch(
                skill_name=skill.normalized_name,
                importance=skill.importance,
                support_score=support_score,
                status=_score_status(support_score),
                evidences=skill_evidences,
            )
        )
    return matches


def calculate_overall_score(matches: list[SkillMatch]) -> float:
    """按岗位重要程度计算 0 到 100 的加权匹配分。"""

    if not matches:
        return 0.0
    weighted_total = sum(
        match.support_score * IMPORTANCE_WEIGHTS[match.importance] for match in matches
    )
    total_weight = sum(IMPORTANCE_WEIGHTS[match.importance] for match in matches)
    return round(weighted_total / total_weight, 1)


def _score_status(score: float) -> SkillMatchStatus:
    if score >= 70:
        return SkillMatchStatus.STRONG
    if score >= 40:
        return SkillMatchStatus.PARTIAL
    return SkillMatchStatus.GAP
