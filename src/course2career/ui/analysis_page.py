import pandas as pd
import streamlit as st
from pydantic import ValidationError

from course2career.access_services import (
    AIUsageService,
    AnalysisRecordService,
    QuotaExceededError,
)
from course2career.analysis_service import analyze_courses_for_job
from course2career.api_key_service import APIKeyService
from course2career.config import Settings
from course2career.course_parser import (
    CourseFileValidationError,
    create_course_template,
    read_course_excel,
)
from course2career.jd_analyzer import JDAnalysisError, analyze_job_description
from course2career.llm_client import LLMClientError
from course2career.llm_provider import ProviderName
from course2career.llm_providers import ProviderError
from course2career.models import JobAnalysis, JobSkill
from course2career.permissions import (
    Permission,
    PermissionDeniedError,
    Plan,
    Principal,
    Role,
    authorize,
)
from course2career.provider_factory import LLMProviderFactory
from course2career.report_exporter import (
    export_markdown,
    export_skill_matches_csv,
)


def render_analysis_page(
    principal: Principal,
    settings: Settings,
    provider_factory: LLMProviderFactory,
    usage_service: AIUsageService,
    record_service: AnalysisRecordService,
    api_key_service: APIKeyService | None,
    guest_session_id: str,
) -> None:
    st.title("个人分析")
    st.caption("课程导入、岗位技能确认、匹配结果和学习路线集中在一个流程中。")

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

    with st.container(border=True):
        st.markdown("## 2. 提取岗位技能")
        jd_text = st.text_area(
            "目标岗位JD",
            height=220,
            max_chars=12_000,
            placeholder="粘贴岗位名称、岗位职责和任职要求。",
        )
        analysis_mode = st.radio(
            "技能提取模式",
            [
                "本地规则",
                "系统AI",
                *(
                    ["开发者API Key"]
                    if principal.plan in {Plan.DEVELOPER, Plan.ADMIN}
                    and api_key_service is not None
                    else []
                ),
            ],
            horizontal=True,
            help="本地规则不消耗AI额度；系统AI使用每日额度。",
        )
        selected_provider = ProviderName.OPENAI
        selected_model = settings.openai_model
        if analysis_mode != "本地规则":
            provider_label = st.selectbox("模型供应商", ["OpenAI", "DeepSeek"])
            if provider_label == "DeepSeek":
                selected_provider = ProviderName.DEEPSEEK
                selected_model = settings.deepseek_model
            st.caption(f"当前模型：{selected_model}")

        if st.button("提取岗位技能", type="primary"):
            usage_id = None
            client = None
            if selected_provider == ProviderName.DEEPSEEK:
                input_cost_per_million = settings.deepseek_input_cost_per_million
                output_cost_per_million = settings.deepseek_output_cost_per_million
            else:
                input_cost_per_million = settings.openai_input_cost_per_million
                output_cost_per_million = settings.openai_output_cost_per_million
            try:
                if analysis_mode == "本地规则":
                    authorize(principal, Permission.USE_DEMO)
                else:
                    key_mode = "user" if analysis_mode == "开发者API Key" else "system"
                    client = provider_factory.create(
                        principal,
                        provider=selected_provider,
                        key_mode=key_mode,
                        model=selected_model,
                    )
                    usage_id = usage_service.start_call(
                        principal,
                        key_mode,
                        selected_model,
                        guest_session_id=guest_session_id,
                        provider=selected_provider.value,
                    )
                st.session_state.job_analysis = analyze_job_description(jd_text, client)
                if usage_id is not None:
                    usage_service.complete_call(
                        usage_id,
                        success=True,
                        usage=client.last_usage if client is not None else None,
                        input_cost_per_million=input_cost_per_million,
                        output_cost_per_million=output_cost_per_million,
                    )
                st.session_state.pop("analysis_report", None)
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
            st.markdown("## 3. 确认技能")
            st.success(f"已提取 {len(job_analysis.skills)} 项技能。")
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
                key="skill_editor",
            )

            if st.button("生成匹配报告", type="primary"):
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
                        report_result = analyze_courses_for_job(
                            courses,
                            confirmed_job,
                        )
                        st.session_state.analysis_report = report_result
                        if principal.role != Role.GUEST:
                            record_service.save(principal, report_result)
                            st.success("分析记录已保存到当前账户。")
                    except (ValidationError, ValueError, TypeError) as exc:
                        st.error(f"技能清单存在无效内容：{exc}")

    report = st.session_state.get("analysis_report")
    if report is not None:
        with st.container(border=True):
            st.markdown("## 4. 匹配结果")
            score_column, strength_column, gap_column = st.columns(3)
            score_column.metric("综合匹配分", f"{report.overall_score:.1f}/100")
            strength_column.metric("优势技能", len(report.strengths))
            gap_column.metric("当前缺口", len(report.gaps))

            match_rows = []
            for match in report.matches:
                course_names = (
                    "、".join(evidence.course_name for evidence in match.evidences)
                    or "无"
                )
                match_rows.append(
                    {
                        "技能": match.skill_name,
                        "重要程度": match.importance.value,
                        "支撑分": match.support_score,
                        "匹配状态": match.status.value,
                        "支撑课程": course_names,
                    }
                )
            st.dataframe(
                pd.DataFrame(match_rows),
                width="stretch",
                hide_index=True,
            )

            left, right = st.columns(2)
            left.markdown("### 当前优势")
            left.write(
                "、".join(report.strengths) if report.strengths else "暂无较强支撑技能"
            )
            right.markdown("### 薄弱技能")
            right.write("、".join(report.gaps) if report.gaps else "暂无明显技能缺口")

            st.markdown("### 推荐学习路线")
            if not report.learning_path:
                st.success("当前没有需要优先补齐的技能。")
            for step in report.learning_path:
                with st.expander(
                    f"{step.priority}. {step.skill_name}"
                    f" · 预计 {step.estimated_hours:g} 小时",
                    expanded=step.priority == 1,
                ):
                    st.write(f"**目标：** {step.objective}")
                    st.write(f"**行动：** {step.action}")
                    st.write(f"**实践项目：** {step.project}")
                    st.write(f"**完成标准：** {step.completion_criteria}")

            st.markdown("### 导出")
            export_left, export_right = st.columns(2)
            export_left.download_button(
                "下载Markdown报告",
                data=export_markdown(report),
                file_name="course2career_report.md",
                mime="text/markdown",
                width="stretch",
            )
            export_right.download_button(
                "下载CSV技能明细",
                data=export_skill_matches_csv(report),
                file_name="course2career_skill_matches.csv",
                mime="text/csv",
                width="stretch",
            )

            with st.expander("查看结果限制"):
                for limitation in report.limitations:
                    st.write(f"- {limitation}")

    if principal.role != Role.GUEST:
        histories = record_service.list_own(principal)
        st.markdown("## 最近分析")
        if histories:
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
        else:
            st.info("完成一次分析后，记录会显示在这里。")
