import pandas as pd
import streamlit as st
from pydantic import ValidationError

from course2career.access_services import (
    AIUsageService,
    AnalysisRecordService,
    QuotaExceededError,
)
from course2career.adaptability import assess_job_adaptability
from course2career.api_key_service import APIKeyService
from course2career.config import Settings
from course2career.course_parser import (
    CourseFileValidationError,
    create_course_template,
    read_course_excel,
)
from course2career.demo_cases import (
    demo_course_frame,
    demo_inputs,
    export_demo_bundle,
    load_demo_cases,
)
from course2career.evidence_display import (
    EVIDENCE_NOTICE,
    eligibility_label,
    skill_sources,
)
from course2career.jd_analyzer import (
    JDAnalysisError,
    analyze_job_description,
    evidence_status,
)
from course2career.llm_client import LLMClientError
from course2career.llm_provider import ProviderName
from course2career.llm_providers import ProviderError
from course2career.model_capability import ModelStatus, Verification, model_capability
from course2career.model_discovery import ModelCatalogService
from course2career.models import AnalysisReport, JobAnalysis, JobSkill
from course2career.permissions import (
    Permission,
    PermissionDeniedError,
    Plan,
    Principal,
    Role,
    authorize,
)
from course2career.provider_factory import LLMProviderFactory
from course2career.provider_profile import ProviderProfileService
from course2career.provider_registry import (
    MAINLAND_PROVIDERS,
    get_provider_preset,
    ui_provider_presets,
)
from course2career.report_exporter import (
    export_adaptability_markdown,
    export_markdown,
    export_skill_matches_csv,
)
from course2career.ui.candidate_profile_form import render_candidate_profile_form


def render_analysis_page(
    principal: Principal,
    settings: Settings,
    provider_factory: LLMProviderFactory,
    usage_service: AIUsageService,
    record_service: AnalysisRecordService,
    api_key_service: APIKeyService | None,
    guest_session_id: str,
    profile_service: ProviderProfileService | None = None,
    catalog_service: ModelCatalogService | None = None,
) -> None:
    st.title("个人分析")
    st.caption("课程、个人经历、岗位要求、五维适配度和能力路线集中在一个流程中。")

    render_demo_cases()

    with st.container(border=True):
        st.markdown("## 1. 导入课程信息")
        st.write("上传课程表，或先下载模板填写。")
        st.download_button(
            "下载课程Excel模板",
            data=create_course_template(),
            file_name="course2career_course_template.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        uploaded_file = st.file_uploader(
            "上传课程Excel",
            type=[".xlsx"],
            help="必填字段：课程名称、学分、成绩、课程类别、自评掌握程度（1到5）。",
            max_upload_size=5,
        )

        courses = []
        if uploaded_file is not None:
            try:
                import_result = read_course_excel(uploaded_file)
            except CourseFileValidationError as exc:
                st.error(str(exc))
            else:
                courses = import_result.courses
                if courses:
                    st.success(f"成功导入 {len(courses)} 门课程。")
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "课程名称": course.name,
                                    "学分": course.credit,
                                    "成绩": course.grade,
                                    "课程类别": course.category,
                                    "自评掌握程度": course.self_assessment,
                                }
                                for course in courses
                            ]
                        ),
                        width="stretch",
                        hide_index=True,
                    )
                else:
                    st.error("文件中没有通过校验的课程，请修正后重新上传。")
                if import_result.errors:
                    st.warning(
                        f"发现 {len(import_result.errors)} 个字段错误，"
                        "错误行不会参与分析。"
                    )
                    st.dataframe(
                        pd.DataFrame(
                            [
                                {
                                    "Excel行号": error.row_number,
                                    "字段": error.field,
                                    "问题": error.message,
                                }
                                for error in import_result.errors
                            ]
                        ),
                        width="stretch",
                        hide_index=True,
                    )

    candidate_profile, job_requirements = render_candidate_profile_form()

    with st.container(border=True):
        st.markdown("## 3. 提取岗位技能")
        jd_text = st.text_area(
            "目标岗位JD",
            height=220,
            max_chars=12_000,
            placeholder="粘贴岗位名称、岗位职责和任职要求。",
        )
        system_providers: list[ProviderName] = []
        if getattr(settings, "system_ai_enabled", True):
            for preset in ui_provider_presets():
                if (
                    preset.system_key_setting
                    and getattr(settings, preset.system_key_setting)
                    and (
                        principal.plan != Plan.FREE
                        or preset.provider_id == ProviderName.DEEPSEEK
                    )
                ):
                    system_providers.append(preset.provider_id)

        analysis_modes = ["本地规则"]
        if system_providers:
            analysis_modes.append("系统AI")
        byok_providers = configured_byok_providers(
            principal, api_key_service, profile_service, catalog_service
        )
        if byok_providers:
            analysis_modes.append("开发者API Key")

        analysis_mode = st.radio(
            "技能提取模式",
            analysis_modes,
            horizontal=True,
            help="本地规则不消耗AI额度；平台已配置模型时才显示系统AI。",
        )
        if not system_providers:
            st.caption(
                "公开 Demo 默认使用“本地规则”，无需注册或平台 AI Key，"
                "可完成完整核心分析流程。"
            )
        selected_provider = ProviderName.OPENAI
        selected_model = get_provider_preset(ProviderName.OPENAI).configured_model(
            settings
        )
        selected_endpoint_id: str | None = None
        profile = None
        if analysis_mode != "本地规则":
            provider_options = (
                system_providers if analysis_mode == "系统AI" else list(byok_providers)
            )
            selected_provider = st.selectbox(
                "模型供应商",
                provider_options,
                format_func=lambda item: get_provider_preset(item).display_name,
            )
            selected_model = get_provider_preset(selected_provider).configured_model(
                settings
            )
            if analysis_mode == "开发者API Key" and profile_service is not None:
                profile = profile_service.get(principal, selected_provider)
                if profile is not None:
                    selected_model = profile.model_id
                    selected_endpoint_id = profile.endpoint_id
            if analysis_mode == "开发者API Key" and catalog_service is not None:
                snapshot = catalog_service.peek(
                    principal,
                    selected_provider,
                    selected_endpoint_id
                    or get_provider_preset(selected_provider).selected_endpoint_id,
                    workspace_id=profile.workspace_id if profile is not None else None,
                )
                if snapshot is not None:
                    with st.expander("查看该供应商全部已发现模型"):
                        if snapshot.stale:
                            st.caption("目录缓存已过期，可到 Provider Hub 手动刷新。")
                        st.dataframe(
                            [
                                {
                                    "模型 ID": item.model_id,
                                    "状态": item.status.value,
                                    "上下文": item.context_window,
                                    "输入价/百万 tokens": item.input_price,
                                    "输出价/百万 tokens": item.output_price,
                                    "币种": item.currency,
                                }
                                for item in snapshot.models
                            ],
                            width="stretch",
                            hide_index=True,
                        )
            if selected_provider == ProviderName.DEEPSEEK:
                if getattr(settings, "deepseek_model_mode", "pinned") == "auto_safe":
                    preference = " → ".join(
                        getattr(
                            settings,
                            "deepseek_model_preference",
                            (selected_model,),
                        )
                    )
                    st.caption(f"DeepSeek Auto-Safe 优先顺序：{preference}")
                else:
                    st.caption(f"当前固定模型：{selected_model}")
            else:
                st.caption(f"当前模型：{selected_model}")
            if analysis_mode == "开发者API Key" and selected_model:
                capability = (
                    catalog_service.selected_model(
                        principal,
                        selected_provider,
                        selected_endpoint_id
                        or get_provider_preset(selected_provider).selected_endpoint_id,
                        selected_model,
                        workspace_id=profile.workspace_id
                        if profile is not None
                        else None,
                    )
                    if catalog_service is not None
                    else model_capability(
                        selected_provider, selected_model, selected_endpoint_id
                    )
                )
                if capability.verification != Verification.VERIFIED:
                    if capability.status == ModelStatus.UNKNOWN:
                        st.warning(
                            "该模型尚无可用的官方目录或真实验证记录；"
                            "请核对模型 ID 和能力后使用。"
                        )
                    else:
                        st.warning(
                            "该模型尚未通过 Course2Career 真实验证；"
                            "可继续尝试，结果需自行核对。"
                        )

        if st.button("提取岗位技能", type="primary"):
            usage_id = None
            client = None
            input_cost_per_million, output_cost_per_million = get_provider_preset(
                selected_provider
            ).cost_rates(settings)
            try:
                if analysis_mode == "本地规则":
                    authorize(principal, Permission.USE_DEMO)
                else:
                    key_mode = "user" if analysis_mode == "开发者API Key" else "system"
                    client = provider_factory.create(
                        principal,
                        provider=selected_provider,
                        key_mode=key_mode,
                        model=selected_model or "",
                        endpoint_id=selected_endpoint_id,
                    )
                    usage_id = usage_service.start_call(
                        principal,
                        key_mode,
                        client.model_name,
                        guest_session_id=guest_session_id,
                        provider=selected_provider.value,
                    )
                st.session_state.job_analysis = analyze_job_description(jd_text, client)
                st.session_state.pop("skill_editor", None)
                if usage_id is not None:
                    usage_service.complete_call(
                        usage_id,
                        success=True,
                        usage=client.last_usage if client is not None else None,
                        input_cost_per_million=input_cost_per_million,
                        output_cost_per_million=output_cost_per_million,
                    )
                st.session_state.pop("analysis_report", None)
                st.session_state.pop("legacy_analysis_report", None)
            except (
                JDAnalysisError,
                LLMClientError,
                ProviderError,
                PermissionDeniedError,
                QuotaExceededError,
            ) as exc:
                if usage_id is not None:
                    usage_service.complete_call(
                        usage_id,
                        success=False,
                        usage=client.last_usage if client is not None else None,
                        input_cost_per_million=input_cost_per_million,
                        output_cost_per_million=output_cost_per_million,
                    )
                st.error(str(exc))

    job_analysis = st.session_state.get("job_analysis")
    edited_skills: pd.DataFrame | None = None
    if job_analysis is not None:
        with st.container(border=True):
            st.markdown("## 4. 确认技能")
            st.success(f"已提取 {len(job_analysis.skills)} 项技能。")
            st.caption(
                "核对状态针对提取时引用；修改后点击生成会按当前JD重新核对。"
                "引用无法定位或技能属于推断时请修正或取消纳入。"
                "保留勾选并生成表示人工确认纳入，仍不代表独立验证。"
                "空引用违反输入契约，必须补充后才能生成。"
            )
            edited_skills = st.data_editor(
                pd.DataFrame(
                    [
                        {
                            "纳入分析": True,
                            "技能": skill.name,
                            "规范技能": skill.normalized_name,
                            "类别": skill.category,
                            "重要程度": skill.importance.value,
                            "JD证据": skill.evidence_text,
                            "依据核对": evidence_status(skill, jd_text),
                        }
                        for skill in job_analysis.skills
                    ]
                ),
                width="stretch",
                hide_index=True,
                num_rows="dynamic",
                column_config={
                    "纳入分析": st.column_config.CheckboxColumn(required=True),
                    "重要程度": st.column_config.SelectboxColumn(
                        options=["核心", "优先", "加分"],
                        required=True,
                    ),
                },
                disabled=["依据核对"],
                key="skill_editor",
            )

            if st.button("生成岗位适配度报告", type="primary"):
                if not courses:
                    st.error("请先上传至少一门有效课程。")
                else:
                    try:
                        selected_rows = edited_skills[
                            edited_skills["纳入分析"] == True  # noqa: E712
                        ]
                        confirmed_skills = [
                            JobSkill(
                                name=row["技能"],
                                normalized_name=row["规范技能"],
                                category=row["类别"],
                                importance=row["重要程度"],
                                evidence_text=row["JD证据"],
                            )
                            for _, row in selected_rows.iterrows()
                        ]
                        if not confirmed_skills:
                            raise ValueError("请至少保留一项岗位技能。")
                        confirmed_job = JobAnalysis(
                            job_title=job_analysis.job_title,
                            skills=confirmed_skills,
                            source="manual",
                        )
                        report_result = assess_job_adaptability(
                            courses=courses,
                            job_analysis=confirmed_job,
                            profile=candidate_profile,
                            requirements=job_requirements,
                        )
                        reference_notes = [
                            f"{skill.normalized_name}："
                            f"{evidence_status(skill, jd_text)}"
                            for skill in confirmed_skills
                        ]
                        report_result = report_result.model_copy(
                            update={
                                "limitations": [
                                    *report_result.limitations,
                                    "JD依据核对（生成时；保留项由用户确认纳入）：",
                                    *reference_notes,
                                ],
                            }
                        )
                        if any("待确认" in note for note in reference_notes):
                            st.warning(
                                "部分引用或技能关联仍待确认；本次按人工保留清单评分。请在结果限制中核对。"
                            )
                        st.session_state.analysis_report = report_result
                        st.session_state.pop("legacy_analysis_report", None)
                        if principal.role != Role.GUEST:
                            record_service.save(principal, report_result)
                            st.success("分析记录已保存到当前账户。")
                    except (ValidationError, ValueError, TypeError) as exc:
                        st.error(f"技能清单存在无效内容：{exc}")

    report = st.session_state.get("analysis_report")
    if report is not None:
        render_adaptability_report(report)

    legacy_report = st.session_state.get("legacy_analysis_report")
    if isinstance(legacy_report, AnalysisReport):
        with st.container(border=True):
            st.markdown("## 5. 旧版技能匹配报告")
            st.metric("综合匹配分", f"{legacy_report.overall_score:.1f}/100")
            st.caption(
                "这是 Career Adaptability Model v2.1 上线前保存的旧版报告。"
                "系统按原始口径展示，不会将旧分数伪装成五维岗位适配度。"
            )

            st.markdown("### 技能证据明细")
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "技能": match.skill_name,
                            "重要程度": match.importance.value,
                            "支撑分": match.support_score,
                            "匹配状态": match.status.value,
                            "支撑课程": "、".join(
                                evidence.course_name for evidence in match.evidences
                            )
                            or "无",
                        }
                        for match in legacy_report.matches
                    ]
                ),
                width="stretch",
                hide_index=True,
            )

            left, right = st.columns(2)
            left.markdown("### 当前优势")
            left.write(
                "、".join(legacy_report.strengths)
                if legacy_report.strengths
                else "暂无较强支撑技能"
            )
            right.markdown("### 技能缺口")
            right.write(
                "、".join(legacy_report.gaps)
                if legacy_report.gaps
                else "暂无明显技能缺口"
            )

            st.markdown("### 导出")
            export_left, export_right = st.columns(2)
            export_left.download_button(
                "下载旧版Markdown报告",
                data=export_markdown(legacy_report),
                file_name="course2career_legacy_report.md",
                mime="text/markdown",
                width="stretch",
            )
            export_right.download_button(
                "下载CSV技能明细",
                key="legacy_csv_report",
                data=export_skill_matches_csv(legacy_report),
                file_name="course2career_legacy_skill_matches.csv",
                mime="text/csv",
                width="stretch",
            )

            with st.expander("查看结果限制"):
                for limitation in legacy_report.limitations:
                    st.write(f"- {limitation}")

    if principal.role != Role.GUEST:
        histories = record_service.list_own(principal)
        st.markdown("## 最近分析")
        if histories:
            st.caption(
                "页面刷新后可在此重新打开已保存的报告；"
                "课程文件和 JD 原文不会被重复保存。"
            )
            st.dataframe(
                pd.DataFrame(
                    [
                        {
                            "岗位": history.job_title or "未命名岗位",
                            "匹配分": history.match_score,
                            "分析时间": history.created_time,
                        }
                        for history in histories[:5]
                    ]
                ),
                width="stretch",
                hide_index=True,
            )
            visible_histories = histories[:5]
            history_by_id = {history.id: history for history in visible_histories}
            selected_history_id = st.selectbox(
                "选择一份历史报告",
                options=list(history_by_id),
                format_func=lambda record_id: (
                    f"{history_by_id[record_id].created_time} · "
                    f"{history_by_id[record_id].job_title or '未命名岗位'} · "
                    f"{history_by_id[record_id].match_score:.1f} 分 · "
                    f"#{record_id[:8]}"
                ),
                key="history_report_selector",
            )
            if st.button("重新打开这份报告", key="restore_history_report"):
                stored_analysis = record_service.get_own(
                    principal,
                    selected_history_id,
                )
                if stored_analysis is None:
                    st.error("未找到这份历史报告，请刷新历史列表后重试。")
                else:
                    if isinstance(stored_analysis.report, AnalysisReport):
                        st.session_state.legacy_analysis_report = stored_analysis.report
                        st.session_state.pop("analysis_report", None)
                    else:
                        st.session_state.analysis_report = stored_analysis.report
                        st.session_state.pop("legacy_analysis_report", None)
                    st.success("已恢复历史报告。课程和 JD 输入不会自动回填。")
                    st.rerun()
        else:
            st.info("完成一次分析后，记录会显示在这里。")


def render_adaptability_report(report, key_prefix="") -> None:
    with st.container(border=True):
        st.markdown("## 5. 岗位适配度结果")
        score_column, gate_column, completeness_column, confidence_column = st.columns(
            4
        )
        score_column.metric("岗位适配度", f"{report.overall_score:.1f}/100")
        gate_column.metric("硬门槛", eligibility_label(report.eligibility))
        completeness_column.metric("资料完整度", f"{report.data_completeness:.0f}%")
        confidence_column.metric("资料完整度等级", report.confidence)
        st.caption(
            f"硬门槛：{eligibility_label(report.eligibility)}。"
            "资料完整度仅反映填写情况，不表示材料经过核验。"
        )
        st.caption(
            "岗位适配度用于比较当前证据与岗位要求，"
            "不代表录用概率、面试通过率或个人能力上限。"
        )

        st.markdown("### 五维评分")
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "维度": "技术技能匹配",
                        "得分": report.dimension_scores.technical,
                        "权重": "25%",
                    },
                    {
                        "维度": "教育与学术背景",
                        "得分": report.dimension_scores.education,
                        "权重": "20%",
                    },
                    {
                        "维度": "项目实践能力",
                        "得分": report.dimension_scores.project,
                        "权重": "20%",
                    },
                    {
                        "维度": "实习实践经验",
                        "得分": report.dimension_scores.internship,
                        "权重": "25%",
                    },
                    {
                        "维度": "学习潜力与就业条件",
                        "得分": report.dimension_scores.potential,
                        "权重": "10%",
                    },
                ]
            ),
            width="stretch",
            hide_index=True,
        )

        st.markdown("### 为什么是这个分数？")
        contribution_rows = [
            {
                "证据或缺口": "大学生岗位适配度解释基准",
                "分数影响": "+50.0",
                "原因": "中性解释基准",
            }
        ]
        contribution_rows.extend(
            {
                "证据或缺口": item.label,
                "分数影响": f"{item.points:+.1f}",
                "原因": item.reason,
            }
            for item in sorted(
                report.contributions,
                key=lambda value: abs(value.points),
                reverse=True,
            )
        )
        st.dataframe(
            pd.DataFrame(contribution_rows),
            width="stretch",
            hide_index=True,
        )

        with st.expander("查看岗位硬门槛"):
            if report.eligibility.checks:
                for check in report.eligibility.checks:
                    st.write(
                        f"- **{check.label}：{check.status.value}** — {check.reason}"
                    )
            else:
                st.write("- 当前JD未设置可结构化核验的硬门槛。")

        match_rows = []
        for match in report.matches:
            course_names = (
                "、".join(evidence.course_name for evidence in match.evidences) or "无"
            )
            match_rows.append(
                {
                    "技能": match.skill_name,
                    "重要程度": match.importance.value,
                    "支撑分": match.support_score,
                    "匹配状态": match.status.value,
                    "支撑课程": course_names,
                    "材料与来源": "；".join(skill_sources(match)),
                }
            )
        st.markdown("### 技能证据明细")
        st.caption(EVIDENCE_NOTICE)
        st.dataframe(
            pd.DataFrame(match_rows),
            width="stretch",
            hide_index=True,
        )
        with st.expander("逐项阅读完整材料来源"):
            for match in report.matches:
                st.write(f"**{match.skill_name}**")
                for source in skill_sources(match):
                    st.write(f"- {source}")

        left, right = st.columns(2)
        left.markdown("### 当前优势")
        left.write(
            "、".join(report.strengths) if report.strengths else "暂无较强支撑技能"
        )
        right.markdown("### 薄弱技能")
        right.write("、".join(report.gaps) if report.gaps else "暂无明显技能缺口")

        st.markdown("### 推荐能力建设路线")
        if not report.learning_modules:
            st.success("当前没有需要优先补齐的技能。")
        for module in report.learning_modules:
            with st.expander(
                f"{module.priority}. {module.name}",
                expanded=module.priority == 1,
            ):
                st.write(f"**对应缺口：** {'、'.join(module.related_gaps)}")
                st.write(f"**目标：** {module.objective}")
                st.write(f"**任务：** {module.task or '历史报告未记录具体任务'}")
                st.write(f"**交付物：** {module.evidence_goal}")
                st.write(
                    "**验收标准：** "
                    f"{module.completion_criteria or '历史报告未记录验收标准'}"
                )

        st.markdown("### 导出")
        export_left, export_right = st.columns(2)
        export_left.download_button(
            "下载Markdown报告",
            key=f"{key_prefix}markdown_report",
            data=export_adaptability_markdown(report),
            file_name="course2career_report.md",
            mime="text/markdown",
            width="stretch",
        )
        export_right.download_button(
            "下载CSV技能明细",
            key=f"{key_prefix}csv_report",
            data=export_skill_matches_csv(report),
            file_name="course2career_skill_matches.csv",
            mime="text/csv",
            width="stretch",
        )

        with st.expander("查看结果限制"):
            for limitation in report.limitations:
                st.write(f"- {limitation}")


def render_demo_cases() -> None:
    with st.expander("三个求职方向合成演示（无需登录或AI）"):
        st.warning("合成演示，不代表真实岗位或候选人")
        st.caption("这里独立运行预设规则，不回填或覆盖下方未保存的课程、JD和个人资料。")
        cases = {case["id"]: case for case in load_demo_cases()}
        case_id = st.selectbox(
            "选择合成案例", list(cases), format_func=lambda value: cases[value]["title"]
        )
        case = cases[case_id]
        st.write(f"**用户任务：** {case['task']}")
        st.code(case["jd"], language=None)
        st.dataframe(demo_course_frame(case), hide_index=True, width="stretch")
        st.json(
            {"候选人资料": case["profile"], "岗位门槛": case["requirements"]},
            expanded=False,
        )
        st.write(f"**预期关键解释：** {case['expected']}")
        st.caption(case["boundary"])
        st.download_button(
            "下载合成案例输入包",
            export_demo_bundle(case),
            file_name=f"{case_id}.zip",
            mime="application/zip",
        )
        if st.button("运行合成规则演示"):
            courses, profile, requirements = demo_inputs(case)
            job = analyze_job_description(case["jd"])
            report = assess_job_adaptability(courses, job, profile, requirements)
            report = report.model_copy(
                update={
                    "limitations": [case["boundary"], *report.limitations],
                }
            )
            st.session_state.demo_result = (case_id, report)
        if st.button("重新开始合成演示"):
            st.session_state.pop("demo_result", None)
        saved = st.session_state.get("demo_result")
    if saved is not None and saved[0] == case_id:
        # 与真实输入报告共用渲染器；演示仅保存独立会话结果。
        render_adaptability_report(saved[1], key_prefix="demo_")


def configured_byok_providers(
    principal: Principal,
    api_key_service: APIKeyService | None,
    profile_service: ProviderProfileService | None,
    catalog_service: ModelCatalogService | None = None,
) -> tuple[ProviderName, ...]:
    if api_key_service is None:
        return ()
    try:
        authorize(principal, Permission.USE_OWN_API_KEY)
        saved = {item.provider for item in api_key_service.list_keys(principal)}
        profiles = (
            {
                ProviderName(item.provider): item
                for item in profile_service.list(principal)
            }
            if profile_service is not None
            else {}
        )
    except PermissionDeniedError:
        return ()
    ranked: list[tuple[int, int, ProviderName]] = []
    for order, preset in enumerate(ui_provider_presets()):
        provider = preset.provider_id
        if provider not in saved:
            continue
        profile = profiles.get(provider)
        model = profile.model_id if profile is not None else preset.default_model
        if not model:
            continue
        endpoint = (
            profile.endpoint_id if profile is not None else preset.selected_endpoint_id
        )
        capability = (
            catalog_service.selected_model(
                principal,
                provider,
                endpoint,
                model,
                workspace_id=profile.workspace_id if profile is not None else None,
            )
            if catalog_service is not None
            else model_capability(provider, model, endpoint)
        )
        if capability.status in {ModelStatus.UNSUPPORTED, ModelStatus.RETIRED}:
            continue
        group = 0 if provider in MAINLAND_PROVIDERS else 1
        status_rank = {
            ModelStatus.VERIFIED: 0,
            ModelStatus.CAPABILITY_ELIGIBLE: 1,
            ModelStatus.UNVERIFIED: 2,
        }.get(capability.status, 3)
        ranked.append((group * 10 + status_rank, order, provider))
    return tuple(item[2] for item in sorted(ranked))
