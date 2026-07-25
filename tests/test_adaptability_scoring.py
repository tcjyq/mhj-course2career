import pytest

from course2career.adaptability import assess_job_adaptability
from course2career.models import (
    CandidateProfile,
    Course,
    DegreeLevel,
    EducationProfile,
    EligibilityStatus,
    InstitutionTier,
    InternshipExperience,
    JobAnalysis,
    JobRequirements,
    JobSkill,
    PotentialProfile,
    ProjectExperience,
    SkillImportance,
)


def _job() -> JobAnalysis:
    return JobAnalysis(
        job_title="AI大模型应用开发实习生",
        source="manual",
        skills=[
            JobSkill(
                name="Python",
                normalized_name="Python",
                category="编程基础",
                importance=SkillImportance.CORE,
                evidence_text="熟悉 Python",
            ),
            JobSkill(
                name="RAG",
                normalized_name="RAG",
                category="AI应用",
                importance=SkillImportance.CORE,
                evidence_text="具有 RAG 项目经验",
            ),
            JobSkill(
                name="Docker",
                normalized_name="Docker",
                category="工程能力",
                importance=SkillImportance.PREFERRED,
                evidence_text="了解 Docker 部署",
            ),
        ],
    )


def _courses() -> list[Course]:
    return [
        Course(
            name="Python程序设计",
            credit=3,
            grade=88,
            category="专业必修",
            self_assessment=4,
        ),
        Course(
            name="数据库原理",
            credit=3,
            grade=82,
            category="专业必修",
            self_assessment=3,
        ),
    ]


def _profile() -> CandidateProfile:
    return CandidateProfile(
        education=EducationProfile(
            degree=DegreeLevel.BACHELOR,
            institution_tier=InstitutionTier.PUBLIC_UNDERGRADUATE,
            major="信息管理与信息系统",
            core_course_average=82,
        ),
        projects=[
            ProjectExperience(
                name="Course2Career",
                skills=["Python", "大模型API", "结构化输出", "测试"],
                relevance=88,
                completeness=92,
                technical_depth=78,
                ownership=95,
                verifiability=92,
                iteration=90,
            )
        ],
        internships=[
            InternshipExperience(
                name="GIS数据核验实习",
                company="某地理信息企业",
                skills=["数据处理", "业务理解", "Excel"],
                relevance=45,
                work_depth=50,
                outcomes=55,
                employer_signal=65,
                duration_months=2,
            )
        ],
        potential=PotentialProfile(
            learning_distance=72,
            growth_trajectory=88,
            job_readiness=76,
            motivation=90,
            city_opportunity=75,
        ),
    )


def _realistic_ai_job() -> JobAnalysis:
    return JobAnalysis(
        job_title="AI大模型应用开发实习生",
        source="manual",
        skills=[
            JobSkill(
                name=name,
                normalized_name=name,
                category=category,
                importance=importance,
                evidence_text=evidence,
            )
            for name, category, importance, evidence in [
                ("Python", "编程基础", SkillImportance.CORE, "熟悉Python"),
                ("FastAPI", "后端开发", SkillImportance.CORE, "熟悉FastAPI"),
                ("SQL", "数据能力", SkillImportance.CORE, "掌握SQL"),
                ("RAG", "AI应用", SkillImportance.CORE, "了解RAG"),
                (
                    "大模型API",
                    "AI应用",
                    SkillImportance.PREFERRED,
                    "有大模型API经验",
                ),
                ("Git", "工程能力", SkillImportance.PREFERRED, "使用Git"),
                ("Docker", "工程能力", SkillImportance.PREFERRED, "了解Docker"),
            ]
        ],
    )


def _realistic_courses() -> list[Course]:
    return [
        Course(
            name=name,
            credit=credit,
            grade=grade,
            category=category,
            self_assessment=self_assessment,
        )
        for name, credit, grade, category, self_assessment in [
            ("Python程序设计", 3, 86, "专业必修", 4),
            ("数据库原理", 3, 82, "专业必修", 3),
            ("Web后端开发", 3, 84, "专业选修", 3),
            ("数据结构", 4, 80, "专业必修", 3),
            ("数据科学基础", 3, 85, "专业必修", 3),
            ("数据挖掘原理与方法", 3, 88, "专业必修", 3),
            ("信息系统分析与设计", 3, 85, "专业必修", 4),
            ("计算机网络", 3, 76, "专业必修", 2),
        ]
    ]


def test_missing_skill_uses_trainability_floor_instead_of_zero() -> None:
    result = assess_job_adaptability(
        courses=_courses(),
        job_analysis=_job(),
        profile=_profile(),
        requirements=JobRequirements(minimum_degree=DegreeLevel.BACHELOR),
    )

    rag = next(match for match in result.matches if match.skill_name == "RAG")

    assert rag.support_score == 15
    assert result.dimension_scores.technical > 0


def test_explanation_ledger_reconciles_exactly_to_final_score() -> None:
    result = assess_job_adaptability(
        courses=_courses(),
        job_analysis=_job(),
        profile=_profile(),
        requirements=JobRequirements(minimum_degree=DegreeLevel.BACHELOR),
    )

    explained_score = 50 + sum(item.points for item in result.contributions)

    assert explained_score == pytest.approx(result.overall_score, abs=0.11)
    assert any(item.label == "Course2Career项目实践" for item in result.contributions)
    assert any(item.label == "缺少RAG直接证据" for item in result.contributions)


def test_projects_internships_and_potential_can_compensate_for_skill_gaps() -> None:
    strong_profile = assess_job_adaptability(
        courses=_courses(),
        job_analysis=_job(),
        profile=_profile(),
        requirements=JobRequirements(minimum_degree=DegreeLevel.BACHELOR),
    )
    no_evidence_profile = assess_job_adaptability(
        courses=_courses(),
        job_analysis=_job(),
        profile=CandidateProfile(
            education=_profile().education,
            projects=[],
            internships=[],
            potential=PotentialProfile(
                learning_distance=40,
                growth_trajectory=40,
                job_readiness=40,
                motivation=50,
                city_opportunity=50,
            ),
        ),
        requirements=JobRequirements(minimum_degree=DegreeLevel.BACHELOR),
    )

    assert strong_profile.overall_score > no_evidence_profile.overall_score + 15


def test_degree_gate_is_reported_separately_from_adaptability_score() -> None:
    result = assess_job_adaptability(
        courses=_courses(),
        job_analysis=_job(),
        profile=_profile(),
        requirements=JobRequirements(minimum_degree=DegreeLevel.MASTER),
    )

    assert result.eligibility.status == EligibilityStatus.FAIL
    assert result.overall_score > 0
    assert any("最低学历" in item.label for item in result.eligibility.checks)


def test_internship_availability_gate_is_explainable() -> None:
    profile = _profile().model_copy(
        update={
            "graduation_year": 2027,
            "available_days_per_week": 3,
            "available_months": 2,
            "preferred_cities": ["无锡", "苏州"],
        }
    )

    result = assess_job_adaptability(
        courses=_courses(),
        job_analysis=_job(),
        profile=profile,
        requirements=JobRequirements(
            minimum_degree=DegreeLevel.BACHELOR,
            required_graduation_years=[2027],
            minimum_days_per_week=4,
            minimum_months=3,
            work_city="上海",
        ),
    )

    assert result.eligibility.status == EligibilityStatus.FAIL
    assert {item.label for item in result.eligibility.checks} >= {
        "毕业年份",
        "每周到岗时间",
        "连续实习时长",
        "工作城市",
    }


def test_representative_ai_application_student_scores_in_potential_range() -> None:
    result = assess_job_adaptability(
        courses=_courses(),
        job_analysis=_job(),
        profile=_profile(),
        requirements=JobRequirements(minimum_degree=DegreeLevel.BACHELOR),
    )

    assert 50 <= result.overall_score <= 70


def test_unknown_profile_sections_reduce_completeness_without_becoming_zero() -> None:
    result = assess_job_adaptability(
        courses=_courses(),
        job_analysis=_job(),
        profile=CandidateProfile(),
        requirements=JobRequirements(),
    )

    assert 0 < result.data_completeness < 60
    assert result.overall_score > 0
    assert result.confidence == "信息不足"


def test_learning_route_is_grouped_into_at_most_eight_modules() -> None:
    result = assess_job_adaptability(
        courses=_courses(),
        job_analysis=_job(),
        profile=_profile(),
        requirements=JobRequirements(minimum_degree=DegreeLevel.BACHELOR),
    )

    assert 1 <= len(result.learning_modules) <= 8
    assert all(module.related_gaps for module in result.learning_modules)


def test_related_project_skill_provides_limited_transfer_evidence() -> None:
    job = JobAnalysis(
        job_title="Python后端开发实习生",
        source="manual",
        skills=[
            JobSkill(
                name="FastAPI",
                normalized_name="FastAPI",
                category="后端开发",
                importance=SkillImportance.CORE,
                evidence_text="熟悉FastAPI",
            )
        ],
    )
    profile = CandidateProfile(
        projects=[
            ProjectExperience(
                name="课程管理系统",
                skills=["Python", "Web后端"],
                relevance=75,
                completeness=80,
                technical_depth=65,
                ownership=85,
                verifiability=70,
                iteration=60,
            )
        ]
    )

    result = assess_job_adaptability(
        courses=[],
        job_analysis=job,
        profile=profile,
        requirements=JobRequirements(),
    )

    assert 40 <= result.matches[0].support_score <= 65


def test_related_course_skills_can_transfer_to_fastapi() -> None:
    job = JobAnalysis(
        job_title="Python后端开发实习生",
        source="manual",
        skills=[
            JobSkill(
                name="FastAPI",
                normalized_name="FastAPI",
                category="后端开发",
                importance=SkillImportance.CORE,
                evidence_text="熟悉FastAPI",
            )
        ],
    )
    courses = [
        Course(
            name="Python程序设计",
            credit=3,
            grade=86,
            category="专业必修",
            self_assessment=4,
        ),
        Course(
            name="Web后端开发",
            credit=3,
            grade=84,
            category="专业选修",
            self_assessment=3,
        ),
    ]

    result = assess_job_adaptability(
        courses=courses,
        job_analysis=job,
        profile=CandidateProfile(),
        requirements=JobRequirements(),
    )

    assert 45 <= result.matches[0].support_score <= 65
    assert any(
        "课程迁移" in evidence
        for item in result.contributions
        for evidence in item.evidence
    )


def test_realistic_ai_internship_case_is_explainable_and_not_overly_harsh() -> None:
    profile = _profile().model_copy(
        update={
            "graduation_year": 2027,
            "available_days_per_week": 4,
            "available_months": 4,
            "preferred_cities": ["无锡", "苏州", "上海"],
        }
    )

    result = assess_job_adaptability(
        courses=_realistic_courses(),
        job_analysis=_realistic_ai_job(),
        profile=profile,
        requirements=JobRequirements(
            minimum_degree=DegreeLevel.BACHELOR,
            required_graduation_years=[2027],
            required_major_keywords=["计算机", "软件工程", "信息管理"],
            minimum_days_per_week=4,
            minimum_months=3,
            work_city="上海",
        ),
    )

    assert result.eligibility.status == EligibilityStatus.PASS
    assert 55 <= result.overall_score <= 75
    assert 50 + sum(item.points for item in result.contributions) == pytest.approx(
        result.overall_score,
        abs=0.11,
    )
    assert (
        next(
            match for match in result.matches if match.skill_name == "SQL"
        ).support_score
        > 50
    )
    assert (
        next(
            match for match in result.matches if match.skill_name == "FastAPI"
        ).support_score
        >= 45
    )
    assert (
        next(
            match for match in result.matches if match.skill_name == "Git"
        ).support_score
        == 15
    )
