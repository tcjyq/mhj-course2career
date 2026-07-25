import streamlit as st


def render_home_page() -> None:
    st.markdown('<p class="c2c-kicker">Course2Career</p>', unsafe_allow_html=True)
    st.title("把学过的课程，翻译成求职能力")
    st.markdown(
        """
        <p class="c2c-lead">
        导入课程成绩，粘贴目标岗位JD。系统会提取岗位技能、寻找课程证据，
        并给出可解释的匹配结果与学习路线。
        </p>
        """,
        unsafe_allow_html=True,
    )

    introduction, output = st.columns([1.35, 1], gap="large")
    with introduction:
        st.markdown("## 它解决什么问题")
        st.write(
            "大学课程名称、成绩和招聘要求通常使用两套语言。"
            "Course2Career把课程学习记录转换为岗位技能证据，帮助你判断"
            "哪些能力已经具备、哪些仍需补齐。"
        )
        st.write("AI只负责理解JD语义；课程映射、评分和报告由可复核的Python规则完成。")
    with output:
        with st.container(border=True):
            st.markdown("### 一次分析会得到")
            st.write("岗位技能清单与原文证据")
            st.write("课程对技能的支撑关系")
            st.write("综合匹配度与能力缺口")
            st.write("按优先级排列的学习路线")

    st.markdown('<div class="c2c-rule"></div>', unsafe_allow_html=True)
    st.markdown("## 使用流程")
    steps = [
        ("01", "导入课程", "下载模板并上传课程、学分、成绩与自评。"),
        ("02", "粘贴JD", "使用本地规则或AI提取目标岗位技能。"),
        ("03", "人工确认", "编辑技能名称、重要程度和分析范围。"),
        ("04", "生成报告", "查看匹配结果、差距和学习路线。"),
    ]
    columns = st.columns(4)
    for column, (number, title, description) in zip(columns, steps, strict=True):
        with column:
            with st.container(border=True):
                st.caption(number)
                st.markdown(f"### {title}")
                st.write(description)

    st.markdown('<div class="c2c-rule"></div>', unsafe_allow_html=True)
    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("## 适合谁")
        st.write("正在准备实习、校招或转岗的大学生。")
        st.write("希望梳理课程价值和技能证据的求职者。")
    with right:
        st.markdown("## 从哪里开始")
        st.write("游客可以直接进入“个人分析”体验本地规则和有限AI额度。")
        st.write("登录后可以保存历史记录，并在“AI额度”查看每日使用情况。")
