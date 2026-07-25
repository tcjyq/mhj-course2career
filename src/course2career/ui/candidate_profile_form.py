import streamlit as st

from course2career.models import (
    CandidateProfile,
    DegreeLevel,
    EducationProfile,
    InstitutionTier,
    InternshipExperience,
    JobRequirements,
    PotentialProfile,
    ProjectExperience,
)


def render_candidate_profile_form() -> tuple[CandidateProfile, JobRequirements]:
    """收集 v2.1 所需的教育、项目、实习与成长信息。"""

    with st.container(border=True):
        st.markdown("## 2. 完善岗位适配度资料")
        st.caption(
            "教育、项目、实习和成长信息用于解释岗位适配度；"
            "未填写不会按零分处理，但会降低结果可信度。"
        )

        education = _render_education()
        projects = _render_projects()
        internships = _render_internships()
        potential = _render_potential()
        availability, requirement_values = _render_hard_requirements()

    return (
        CandidateProfile(
            education=education,
            projects=projects,
            internships=internships,
            potential=potential,
            **availability,
        ),
        JobRequirements(
            minimum_degree=st.session_state.get("c2c_minimum_degree"),
            **requirement_values,
        ),
    )


def _render_education() -> EducationProfile | None:
    with st.expander("教育与学术背景", expanded=True):
        include = st.checkbox("纳入教育背景评估", value=True)
        if not include:
            return None
        left, right = st.columns(2)
        degree = left.selectbox(
            "当前学历",
            list(DegreeLevel),
            index=2,
            format_func=lambda item: item.value,
        )
        institution = right.selectbox(
            "院校类型",
            list(InstitutionTier),
            index=list(InstitutionTier).index(InstitutionTier.PUBLIC_UNDERGRADUATE),
            format_func=lambda item: item.value,
        )
        major = st.text_input("专业", placeholder="例如：信息管理与信息系统").strip()
        core_average = st.number_input(
            "目标岗位相关核心课程平均分",
            min_value=0.0,
            max_value=100.0,
            value=0.0,
            step=1.0,
            help="不知道时可填0，系统会将该项视为未提供。",
        )
        st.selectbox(
            "岗位最低学历要求",
            [None, *DegreeLevel],
            index=0,
            format_func=lambda item: "未明确" if item is None else item.value,
            key="c2c_minimum_degree",
        )
        if not major:
            return None
        return EducationProfile(
            degree=degree,
            institution_tier=institution,
            major=major,
            core_course_average=core_average or None,
        )


def _render_projects() -> list[ProjectExperience] | None:
    with st.expander("项目实践"):
        state = st.selectbox(
            "项目填写状态",
            ["暂未填写", "目前没有项目", "填写项目"],
            key="c2c_project_state",
        )
        if state == "暂未填写":
            return None
        if state == "目前没有项目":
            return []
        count = st.number_input("项目数量", min_value=1, max_value=3, value=1, step=1)
        projects: list[ProjectExperience] = []
        for index in range(int(count)):
            st.markdown(f"**项目 {index + 1}**")
            name = st.text_input("项目名称", key=f"c2c_project_name_{index}").strip()
            skills = _split_skills(
                st.text_input(
                    "使用技能（逗号分隔）",
                    key=f"c2c_project_skills_{index}",
                    placeholder="Python, 大模型API, 测试",
                )
            )
            relevance = st.slider(
                "岗位相关性", 0, 100, 70, key=f"c2c_project_relevance_{index}"
            )
            completeness = st.slider(
                "项目完整度", 0, 100, 70, key=f"c2c_project_completeness_{index}"
            )
            technical_depth = st.slider(
                "技术深度", 0, 100, 65, key=f"c2c_project_depth_{index}"
            )
            ownership = st.slider(
                "个人贡献", 0, 100, 80, key=f"c2c_project_ownership_{index}"
            )
            verifiability = st.slider(
                "可验证性", 0, 100, 70, key=f"c2c_project_verify_{index}"
            )
            iteration = st.slider(
                "迭代记录", 0, 100, 60, key=f"c2c_project_iteration_{index}"
            )
            if name:
                projects.append(
                    ProjectExperience(
                        name=name,
                        skills=skills,
                        relevance=relevance,
                        completeness=completeness,
                        technical_depth=technical_depth,
                        ownership=ownership,
                        verifiability=verifiability,
                        iteration=iteration,
                    )
                )
        return projects or None


def _render_internships() -> list[InternshipExperience] | None:
    with st.expander("实习实践"):
        state = st.selectbox(
            "实习填写状态",
            ["暂未填写", "目前没有实习", "填写实习"],
            key="c2c_internship_state",
        )
        if state == "暂未填写":
            return None
        if state == "目前没有实习":
            return []
        count = st.number_input("实习数量", min_value=1, max_value=3, value=1, step=1)
        internships: list[InternshipExperience] = []
        for index in range(int(count)):
            st.markdown(f"**实习 {index + 1}**")
            name = st.text_input("实习岗位", key=f"c2c_internship_name_{index}").strip()
            company = st.text_input(
                "实习企业", key=f"c2c_internship_company_{index}"
            ).strip()
            skills = _split_skills(
                st.text_input(
                    "实习技能（逗号分隔）",
                    key=f"c2c_internship_skills_{index}",
                    placeholder="数据处理, 业务理解, Excel",
                )
            )
            relevance = st.slider(
                "与目标岗位相关性",
                0,
                100,
                60,
                key=f"c2c_internship_relevance_{index}",
            )
            work_depth = st.slider(
                "工作深度", 0, 100, 60, key=f"c2c_internship_depth_{index}"
            )
            outcomes = st.slider(
                "成果可验证性", 0, 100, 60, key=f"c2c_internship_outcomes_{index}"
            )
            employer_signal = st.slider(
                "企业与行业说服力",
                0,
                100,
                60,
                key=f"c2c_internship_signal_{index}",
            )
            duration = st.number_input(
                "持续月数",
                min_value=0.0,
                max_value=60.0,
                value=2.0,
                step=0.5,
                key=f"c2c_internship_duration_{index}",
            )
            if name and company:
                internships.append(
                    InternshipExperience(
                        name=name,
                        company=company,
                        skills=skills,
                        relevance=relevance,
                        work_depth=work_depth,
                        outcomes=outcomes,
                        employer_signal=employer_signal,
                        duration_months=duration,
                    )
                )
        return internships or None


def _render_potential() -> PotentialProfile | None:
    with st.expander("学习潜力与就业条件"):
        include = st.checkbox("纳入成长潜力评估", value=False)
        if not include:
            return None
        learning_distance = st.slider("现有基础到目标岗位的学习可达性", 0, 100, 65)
        growth = st.slider("最近6—12个月成长速度", 0, 100, 70)
        readiness = st.slider("求职准备度", 0, 100, 60)
        motivation = st.slider("对目标岗位的持续投入意愿", 0, 100, 75)
        city = st.slider("意向城市岗位机会与个人灵活度", 0, 100, 65)
        return PotentialProfile(
            learning_distance=learning_distance,
            growth_trajectory=growth,
            job_readiness=readiness,
            motivation=motivation,
            city_opportunity=city,
        )


def _render_hard_requirements() -> tuple[dict[str, object], dict[str, object]]:
    with st.expander("到岗条件与岗位硬门槛"):
        st.caption("只填写JD明确写出的限制；0或留空表示岗位没有明确要求。")
        include_availability = st.checkbox("填写我的到岗条件", value=False)
        if include_availability:
            graduation_year = st.number_input(
                "我的毕业年份",
                min_value=2000,
                max_value=2100,
                value=2027,
                step=1,
            )
            available_days = st.number_input(
                "每周可到岗天数", min_value=0, max_value=7, value=4, step=1
            )
            available_months = st.number_input(
                "可连续实习月数",
                min_value=0.0,
                max_value=60.0,
                value=3.0,
                step=0.5,
            )
            preferred_cities = _split_skills(st.text_input("意向城市（逗号分隔）"))
        else:
            graduation_year = None
            available_days = None
            available_months = None
            preferred_cities = None

        required_year = st.number_input(
            "JD要求的毕业年份（0表示未明确）",
            min_value=0,
            max_value=2100,
            value=0,
            step=1,
        )
        minimum_days = st.number_input(
            "JD要求每周最少到岗天数（0表示未明确）",
            min_value=0,
            max_value=7,
            value=0,
            step=1,
        )
        minimum_months = st.number_input(
            "JD要求最少连续实习月数（0表示未明确）",
            min_value=0.0,
            max_value=60.0,
            value=0.0,
            step=0.5,
        )
        work_city = st.text_input("JD工作城市（留空表示未明确）").strip()
        major_keywords = _split_skills(
            st.text_input(
                "JD明确限制的专业关键词（逗号分隔）",
                placeholder="计算机, 软件工程",
            )
        )

    return (
        {
            "graduation_year": int(graduation_year) if graduation_year else None,
            "available_days_per_week": (
                int(available_days) if available_days is not None else None
            ),
            "available_months": (
                float(available_months) if available_months is not None else None
            ),
            "preferred_cities": preferred_cities,
        },
        {
            "required_graduation_years": [int(required_year)]
            if required_year
            else None,
            "required_major_keywords": major_keywords or None,
            "minimum_days_per_week": int(minimum_days) if minimum_days else None,
            "minimum_months": float(minimum_months) if minimum_months else None,
            "work_city": work_city or None,
        },
    )


def _split_skills(value: str) -> list[str]:
    normalized = value.replace("，", ",")
    return [item.strip() for item in normalized.split(",") if item.strip()]
