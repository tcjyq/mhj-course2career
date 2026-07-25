import json
from collections.abc import Iterable
from pathlib import Path

from course2career.course_skill_mapper import map_courses_to_skills
from course2career.models import (
    AdaptabilityReport,
    CandidateProfile,
    Course,
    DegreeLevel,
    DimensionScores,
    EducationProfile,
    EligibilityCheck,
    EligibilityResult,
    EligibilityStatus,
    InstitutionTier,
    InternshipExperience,
    JobAnalysis,
    JobRequirements,
    LearningModule,
    PotentialProfile,
    ProjectExperience,
    ScoreContribution,
    SkillImportance,
    SkillMatch,
    SkillMatchStatus,
)
from course2career.scoring import build_skill_matches
from course2career.skill_normalizer import normalize_skill_name

DIMENSION_WEIGHTS = {
    "technical": 0.25,
    "education": 0.20,
    "project": 0.20,
    "internship": 0.25,
    "potential": 0.10,
}
IMPORTANCE_WEIGHTS = {
    SkillImportance.CORE: 1.0,
    SkillImportance.PREFERRED: 0.7,
    SkillImportance.BONUS: 0.4,
}
DEGREE_ORDER = {
    DegreeLevel.HIGH_SCHOOL: 0,
    DegreeLevel.ASSOCIATE: 1,
    DegreeLevel.BACHELOR: 2,
    DegreeLevel.MASTER: 3,
    DegreeLevel.DOCTORATE: 4,
}
INSTITUTION_SCORES = {
    InstitutionTier.TOP_985: 95.0,
    InstitutionTier.DOUBLE_FIRST_CLASS: 85.0,
    InstitutionTier.INDUSTRY_RECOGNIZED: 78.0,
    InstitutionTier.STRONG_PUBLIC_UNDERGRADUATE: 72.0,
    InstitutionTier.PUBLIC_UNDERGRADUATE: 65.0,
    InstitutionTier.PRIVATE_UNDERGRADUATE: 55.0,
    InstitutionTier.TOP_VOCATIONAL: 60.0,
    InstitutionTier.VOCATIONAL: 50.0,
    InstitutionTier.OVERSEAS: 50.0,
    InstitutionTier.OTHER: 50.0,
}
TRANSFER_RULES_PATH = (
    Path(__file__).resolve().parents[2] / "data" / "skill_transfer_rules.json"
)


def assess_job_adaptability(
    courses: list[Course],
    job_analysis: JobAnalysis,
    profile: CandidateProfile,
    requirements: JobRequirements,
) -> AdaptabilityReport:
    matches, technical_sources = _build_technical_matches(
        courses, job_analysis, profile
    )
    technical_score, technical_contributions = _score_technical(
        matches, technical_sources
    )
    education_score, education_contributions = _score_education(
        profile.education, requirements, job_analysis.job_title
    )
    project_score, project_contributions = _score_projects(profile.projects)
    internship_score, internship_contributions = _score_internships(profile.internships)
    potential_score, potential_contributions = _score_potential(profile.potential)

    dimensions = DimensionScores(
        technical=technical_score,
        education=education_score,
        project=project_score,
        internship=internship_score,
        potential=potential_score,
    )
    contributions = [
        *technical_contributions,
        *education_contributions,
        *project_contributions,
        *internship_contributions,
        *potential_contributions,
    ]
    overall_score = round(
        sum(
            getattr(dimensions, dimension) * weight
            for dimension, weight in DIMENSION_WEIGHTS.items()
        ),
        1,
    )
    completeness = _data_completeness(courses, profile)

    return AdaptabilityReport(
        job_title=job_analysis.job_title,
        overall_score=overall_score,
        eligibility=_check_eligibility(profile, requirements),
        dimension_scores=dimensions,
        contributions=contributions,
        data_completeness=completeness,
        confidence=_confidence_label(completeness),
        matches=matches,
        strengths=[item.label for item in contributions if item.points >= 1.0][:8],
        gaps=[item.label for item in contributions if item.points <= -1.0][:8],
        learning_modules=_build_learning_modules(matches),
        limitations=[
            "岗位适配度用于比较当前证据与岗位要求，不代表录用概率。",
            "院校与学历仅作为现实市场信号，不代表个人能力上限。",
            "未填写的信息不会按零分处理，但会降低数据完整度和结果可信度。",
        ],
    )


def _build_technical_matches(
    courses: list[Course], job_analysis: JobAnalysis, profile: CandidateProfile
) -> tuple[list[SkillMatch], dict[str, list[str]]]:
    course_evidences = map_courses_to_skills(courses, job_analysis.skills)
    base_matches = build_skill_matches(job_analysis.skills, course_evidences)
    course_scores = _course_skill_scores(courses)
    project_scores = _experience_skill_scores(profile.projects or [])
    internship_scores = _experience_skill_scores(profile.internships or [])
    transfer_rules = _load_transfer_rules()
    matches: list[SkillMatch] = []
    sources_by_skill: dict[str, list[str]] = {}

    for match in base_matches:
        normalized_skill = normalize_skill_name(match.skill_name)
        scored_sources = [
            (evidence.evidence_score, f"课程：{evidence.course_name}")
            for evidence in match.evidences
        ]
        scored_sources.extend(project_scores.get(normalized_skill, []))
        scored_sources.extend(internship_scores.get(normalized_skill, []))
        scored_sources.extend(
            _transfer_scores(
                normalized_skill,
                course_scores,
                transfer_rules,
                source_type="课程迁移",
            )
        )
        scored_sources.extend(
            _transfer_scores(
                normalized_skill,
                project_scores,
                transfer_rules,
                source_type="项目迁移",
            )
        )
        scored_sources.extend(
            _transfer_scores(
                normalized_skill,
                internship_scores,
                transfer_rules,
                source_type="实习迁移",
            )
        )
        support_score = _combine_evidence_scores([score for score, _ in scored_sources])
        sources_by_skill[normalized_skill] = [
            label
            for _, label in sorted(
                scored_sources, reverse=True, key=lambda item: item[0]
            )
        ][:3]
        matches.append(
            match.model_copy(
                update={
                    "support_score": support_score,
                    "status": _match_status(support_score),
                }
            )
        )
    return matches, sources_by_skill


def _load_transfer_rules() -> list[dict[str, object]]:
    with TRANSFER_RULES_PATH.open(encoding="utf-8") as file:
        return list(json.load(file))


def _transfer_scores(
    target_skill: str,
    source_scores: dict[str, list[tuple[float, str]]],
    rules: list[dict[str, object]],
    *,
    source_type: str,
) -> list[tuple[float, str]]:
    scores: list[tuple[float, str]] = []
    for rule in rules:
        if normalize_skill_name(str(rule["target"])) != target_skill:
            continue
        sources = [normalize_skill_name(str(item)) for item in rule["sources"]]
        if not all(source in source_scores for source in sources):
            continue
        source_score = min(
            max(score for score, _ in source_scores[source]) for source in sources
        )
        transfer_score = min(source_score * float(rule["strength"]), 65)
        scores.append(
            (
                round(transfer_score, 1),
                f"{source_type}：{' + '.join(sources)} → {target_skill}",
            )
        )
    return scores


def _course_skill_scores(
    courses: list[Course],
) -> dict[str, list[tuple[float, str]]]:
    result: dict[str, list[tuple[float, str]]] = {}
    for evidence in map_courses_to_skills(courses, None):
        normalized = normalize_skill_name(evidence.skill_name)
        result.setdefault(normalized, []).append(
            (evidence.evidence_score, f"课程：{evidence.course_name}")
        )
    return result


def _experience_skill_scores(
    experiences: Iterable[ProjectExperience | InternshipExperience],
) -> dict[str, list[tuple[float, str]]]:
    result: dict[str, list[tuple[float, str]]] = {}
    for experience in experiences:
        score = (
            _project_quality(experience)
            if isinstance(experience, ProjectExperience)
            else _internship_quality(experience)
        )
        label = (
            f"项目：{experience.name}"
            if isinstance(experience, ProjectExperience)
            else f"实习：{experience.company}·{experience.name}"
        )
        for skill in experience.skills:
            normalized = normalize_skill_name(skill)
            result.setdefault(normalized, []).append((score, label))
    return result


def _combine_evidence_scores(scores: list[float]) -> float:
    if not scores:
        return 15.0
    ordered = sorted(scores, reverse=True)
    combined = ordered[0]
    if len(ordered) > 1:
        combined += ordered[1] * 0.2
    if len(ordered) > 2:
        combined += ordered[2] * 0.1
    return round(min(combined, 100), 1)


def _match_status(score: float) -> SkillMatchStatus:
    if score >= 70:
        return SkillMatchStatus.STRONG
    if score >= 40:
        return SkillMatchStatus.PARTIAL
    return SkillMatchStatus.GAP


def _score_technical(
    matches: list[SkillMatch],
    sources_by_skill: dict[str, list[str]],
) -> tuple[float, list[ScoreContribution]]:
    if not matches:
        return 50.0, []
    total_importance = sum(IMPORTANCE_WEIGHTS[item.importance] for item in matches)
    contributions: list[ScoreContribution] = []
    score = 0.0
    for match in matches:
        factor_weight = IMPORTANCE_WEIGHTS[match.importance] / total_importance
        score += match.support_score * factor_weight
        sources = sources_by_skill.get(match.skill_name, [])
        missing = not sources and match.support_score <= 15
        label = (
            f"缺少{match.skill_name}直接证据"
            if missing
            else f"{sources[0]}支持{match.skill_name}"
        )
        contributions.append(
            ScoreContribution(
                label=label,
                dimension="technical",
                source_type="skill_gap" if match.support_score < 50 else "skill",
                points=round(25 * factor_weight * (match.support_score - 50) / 100, 3),
                reason=(
                    "当前没有直接课程、项目或实习证据，按大学生可学习基础保留15分"
                    if missing
                    else f"当前可验证支撑分为{match.support_score:.1f}"
                ),
                evidence=sources,
                confidence=0.9 if sources else 0.65,
                actionable=match.support_score < 50,
                improvement=(
                    f"通过课程作业或项目补充{match.skill_name}的可验证证据"
                    if match.support_score < 50
                    else None
                ),
            )
        )
    return round(score, 1), contributions


def _score_education(
    education: EducationProfile | None,
    requirements: JobRequirements,
    job_title: str | None,
) -> tuple[float, list[ScoreContribution]]:
    if education is None:
        return 50.0, []

    factor_scores = {
        "学历与岗位要求": _degree_fit_score(education.degree, requirements),
        "院校市场信号": INSTITUTION_SCORES[education.institution_tier],
        "专业相关性": _major_relevance_score(education.major, job_title),
        "核心课程表现": _academic_score(education),
    }
    factor_weights = {
        "学历与岗位要求": 0.30,
        "院校市场信号": 0.30,
        "专业相关性": 0.25,
        "核心课程表现": 0.15,
    }
    score = sum(factor_scores[name] * factor_weights[name] for name in factor_scores)
    contributions = [
        ScoreContribution(
            label=name,
            dimension="education",
            source_type="education",
            points=round(
                20 * factor_weights[name] * (factor_scores[name] - 50) / 100, 3
            ),
            reason=f"{name}评估为{factor_scores[name]:.1f}分",
            evidence=[
                education.degree.value,
                education.institution_tier.value,
                education.major,
            ],
            confidence=0.8,
        )
        for name in factor_scores
    ]
    return round(score, 1), contributions


def _degree_fit_score(degree: DegreeLevel, requirements: JobRequirements) -> float:
    if requirements.minimum_degree is None:
        return 70.0
    difference = DEGREE_ORDER[degree] - DEGREE_ORDER[requirements.minimum_degree]
    if difference < 0:
        return 20.0
    if difference == 0:
        return 85.0
    return 88.0


def _major_relevance_score(major: str, job_title: str | None) -> float:
    normalized = major.casefold()
    title = (job_title or "").casefold()
    if not any(
        token in title for token in ("ai", "大模型", "人工智能", "数据", "开发")
    ):
        return 65.0
    if any(token in normalized for token in ("计算机", "软件", "人工智能", "数据科学")):
        return 95.0
    if "信息管理" in normalized or "信息系统" in normalized:
        return 78.0
    if any(token in normalized for token in ("电子", "自动化", "数学", "统计")):
        return 75.0
    return 45.0


def _academic_score(education: EducationProfile) -> float:
    if education.academic_percentile is not None:
        top_percent = education.academic_percentile
        if top_percent <= 10:
            return 95.0
        if top_percent <= 25:
            return 85.0
        if top_percent <= 50:
            return 70.0
        return 55.0
    if education.core_course_average is not None:
        return education.core_course_average
    return 50.0


def _score_projects(
    projects: list[ProjectExperience] | None,
) -> tuple[float, list[ScoreContribution]]:
    if projects is None:
        return 50.0, []
    if not projects:
        score = 20.0
        label = "缺少项目实践证据"
        evidence: list[str] = []
    else:
        ordered = sorted(
            ((_project_quality(project), project) for project in projects),
            reverse=True,
            key=lambda item: item[0],
        )
        score = _diminishing_score([item[0] for item in ordered])
        label = f"{ordered[0][1].name}项目实践"
        evidence = [item[1].name for item in ordered[:3]]
    contribution = ScoreContribution(
        label=label,
        dimension="project",
        source_type="project" if projects else "project_gap",
        points=round(20 * (score - 50) / 100, 3),
        reason=f"项目相关性、完整度、技术深度、个人贡献和可验证性综合为{score:.1f}分",
        evidence=evidence,
        confidence=0.9 if projects else 0.95,
        actionable=not projects,
        improvement="完成一个可运行、可测试、可演示的岗位相关项目"
        if not projects
        else None,
    )
    return round(score, 1), [contribution]


def _project_quality(project: ProjectExperience) -> float:
    return round(
        project.relevance * 0.25
        + project.completeness * 0.20
        + project.technical_depth * 0.20
        + project.ownership * 0.15
        + project.verifiability * 0.15
        + project.iteration * 0.05,
        1,
    )


def _score_internships(
    internships: list[InternshipExperience] | None,
) -> tuple[float, list[ScoreContribution]]:
    if internships is None:
        return 50.0, []
    if not internships:
        score = 20.0
        label = "缺少实习实践证据"
        evidence: list[str] = []
    else:
        ordered = sorted(
            ((_internship_quality(item), item) for item in internships),
            reverse=True,
            key=lambda item: item[0],
        )
        score = _diminishing_score([item[0] for item in ordered])
        label = f"{ordered[0][1].name}经历"
        evidence = [f"{item[1].company}：{item[1].name}" for item in ordered[:3]]
    contribution = ScoreContribution(
        label=label,
        dimension="internship",
        source_type="internship" if internships else "internship_gap",
        points=round(25 * (score - 50) / 100, 3),
        reason=f"岗位相关性、工作深度、成果、企业信号和时长综合为{score:.1f}分",
        evidence=evidence,
        confidence=0.85 if internships else 0.95,
        actionable=not internships,
        improvement="争取一段与目标岗位相邻且有真实成果的实习"
        if not internships
        else None,
    )
    return round(score, 1), [contribution]


def _internship_quality(internship: InternshipExperience) -> float:
    duration_score = min(internship.duration_months / 6 * 100, 100)
    return round(
        internship.relevance * 0.30
        + internship.work_depth * 0.25
        + internship.outcomes * 0.20
        + internship.employer_signal * 0.15
        + duration_score * 0.10,
        1,
    )


def _diminishing_score(scores: list[float]) -> float:
    if not scores:
        return 20.0
    weights = (0.7, 0.2, 0.1)
    selected = scores[:3]
    used_weight = sum(weights[: len(selected)])
    return round(
        sum(score * weight for score, weight in zip(selected, weights, strict=False))
        / used_weight,
        1,
    )


def _score_potential(
    potential: PotentialProfile | None,
) -> tuple[float, list[ScoreContribution]]:
    if potential is None:
        return 50.0, []
    factors = {
        "技能学习距离": (potential.learning_distance, 0.30),
        "近期成长轨迹": (potential.growth_trajectory, 0.25),
        "求职准备度": (potential.job_readiness, 0.20),
        "岗位投入意愿": (potential.motivation, 0.15),
        "城市岗位机会": (potential.city_opportunity, 0.10),
    }
    score = sum(value * weight for value, weight in factors.values())
    contributions = [
        ScoreContribution(
            label=label,
            dimension="potential",
            source_type="potential",
            points=round(10 * weight * (value - 50) / 100, 3),
            reason=f"{label}评估为{value:.1f}分",
            evidence=[],
            confidence=0.65,
            actionable=value < 50,
        )
        for label, (value, weight) in factors.items()
    ]
    return round(score, 1), contributions


def _check_eligibility(
    profile: CandidateProfile, requirements: JobRequirements
) -> EligibilityResult:
    checks: list[EligibilityCheck] = []
    education = profile.education

    if requirements.minimum_degree is not None:
        if education is None:
            checks.append(
                _eligibility_check(
                    "最低学历",
                    EligibilityStatus.CONDITIONAL,
                    f"岗位要求{requirements.minimum_degree.value}，但尚未填写学历",
                )
            )
        elif DEGREE_ORDER[education.degree] < DEGREE_ORDER[requirements.minimum_degree]:
            checks.append(
                _eligibility_check(
                    "最低学历",
                    EligibilityStatus.FAIL,
                    f"岗位要求{requirements.minimum_degree.value}，"
                    f"当前学历为{education.degree.value}",
                )
            )
        else:
            checks.append(
                _eligibility_check(
                    "最低学历",
                    EligibilityStatus.PASS,
                    f"当前学历满足{requirements.minimum_degree.value}要求",
                )
            )

    if requirements.required_major_keywords:
        if education is None:
            checks.append(
                _eligibility_check(
                    "专业限制",
                    EligibilityStatus.CONDITIONAL,
                    "岗位设置了专业限制，但尚未填写专业",
                )
            )
        else:
            matched = any(
                keyword.casefold() in education.major.casefold()
                for keyword in requirements.required_major_keywords
            )
            checks.append(
                _eligibility_check(
                    "专业限制",
                    EligibilityStatus.PASS if matched else EligibilityStatus.FAIL,
                    (
                        f"当前专业“{education.major}”符合岗位专业关键词"
                        if matched
                        else f"当前专业“{education.major}”未匹配岗位明确专业限制"
                    ),
                )
            )

    optional_checks = [
        _graduation_year_gate(
            profile.graduation_year, requirements.required_graduation_years
        ),
        _minimum_gate(
            "每周到岗时间",
            profile.available_days_per_week,
            requirements.minimum_days_per_week,
            "天/周",
        ),
        _minimum_gate(
            "连续实习时长",
            profile.available_months,
            requirements.minimum_months,
            "个月",
        ),
        _city_gate(profile.preferred_cities, requirements.work_city),
    ]
    checks.extend(check for check in optional_checks if check is not None)

    if any(check.status == EligibilityStatus.FAIL for check in checks):
        status = EligibilityStatus.FAIL
    elif any(check.status == EligibilityStatus.CONDITIONAL for check in checks):
        status = EligibilityStatus.CONDITIONAL
    else:
        status = EligibilityStatus.PASS
    return EligibilityResult(status=status, checks=checks)


def _eligibility_check(
    label: str, status: EligibilityStatus, reason: str
) -> EligibilityCheck:
    return EligibilityCheck(label=label, status=status, reason=reason)


def _graduation_year_gate(
    actual: int | None, allowed: list[int] | None
) -> EligibilityCheck | None:
    if not allowed:
        return None
    if actual is None:
        return _eligibility_check(
            "毕业年份",
            EligibilityStatus.CONDITIONAL,
            f"岗位要求毕业年份为{allowed}，当前未填写",
        )
    return _eligibility_check(
        "毕业年份",
        EligibilityStatus.PASS if actual in allowed else EligibilityStatus.FAIL,
        f"岗位要求毕业年份为{allowed}，当前为{actual}",
    )


def _minimum_gate(
    label: str,
    actual: float | int | None,
    minimum: float | int | None,
    unit: str,
) -> EligibilityCheck | None:
    if minimum is None:
        return None
    if actual is None:
        return _eligibility_check(
            label,
            EligibilityStatus.CONDITIONAL,
            f"岗位至少要求{minimum:g}{unit}，当前未填写",
        )
    return _eligibility_check(
        label,
        EligibilityStatus.PASS if actual >= minimum else EligibilityStatus.FAIL,
        f"岗位至少要求{minimum:g}{unit}，当前可满足{actual:g}{unit}",
    )


def _city_gate(
    preferred_cities: list[str] | None, work_city: str | None
) -> EligibilityCheck | None:
    if not work_city:
        return None
    if preferred_cities is None:
        return _eligibility_check(
            "工作城市",
            EligibilityStatus.CONDITIONAL,
            f"岗位位于{work_city}，当前未填写意向城市",
        )
    matched = any(
        work_city.casefold() in city.casefold()
        or city.casefold() in work_city.casefold()
        for city in preferred_cities
    )
    preferred_label = "、".join(preferred_cities) or "未指定"
    return _eligibility_check(
        "工作城市",
        EligibilityStatus.PASS if matched else EligibilityStatus.FAIL,
        (
            f"岗位城市{work_city}在意向范围内"
            if matched
            else f"岗位位于{work_city}，当前意向为{preferred_label}"
        ),
    )


def _data_completeness(courses: list[Course], profile: CandidateProfile) -> float:
    score = 25.0 if courses else 0.0
    score += 20.0 if profile.education is not None else 0.0
    score += 20.0 if profile.projects is not None else 0.0
    score += 25.0 if profile.internships is not None else 0.0
    score += 10.0 if profile.potential is not None else 0.0
    return score


def _confidence_label(completeness: float) -> str:
    if completeness >= 85:
        return "较高"
    if completeness >= 70:
        return "中等"
    if completeness >= 50:
        return "初步评估"
    return "信息不足"


def _build_learning_modules(matches: list[SkillMatch]) -> list[LearningModule]:
    groups: dict[str, list[str]] = {}
    for match in matches:
        if match.support_score >= 50:
            continue
        module_name = _module_name(match.skill_name)
        groups.setdefault(module_name, []).append(match.skill_name)

    modules: list[LearningModule] = []
    for priority, (name, gaps) in enumerate(list(groups.items())[:8], start=1):
        modules.append(
            LearningModule(
                priority=priority,
                name=name,
                related_gaps=gaps,
                objective=f"把{'、'.join(gaps)}从概念或缺口提升为可验证能力",
                evidence_goal=f"完成一个能够证明{'、'.join(gaps)}的项目模块并补充测试",
            )
        )
    return modules


def _module_name(skill_name: str) -> str:
    normalized = skill_name.casefold()
    if any(token in normalized for token in ("rag", "embedding", "向量", "rerank")):
        return "RAG完整链路"
    if any(token in normalized for token in ("docker", "linux", "部署", "云")):
        return "Docker、Linux与部署"
    if any(token in normalized for token in ("agent", "function", "工具调用")):
        return "Agent与工具调用"
    if any(token in normalized for token in ("fastapi", "rest", "http", "api")):
        return "FastAPI与REST接口"
    if any(token in normalized for token in ("测试", "日志", "异常")):
        return "测试、日志与异常处理"
    if any(token in normalized for token in ("python", "编程")):
        return "Python工程基础"
    return f"{skill_name}能力建设"
