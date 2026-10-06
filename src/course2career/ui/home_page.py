from textwrap import dedent

import streamlit as st


def render_home_page(analysis_page=None) -> None:
    st.markdown(
        '<p class="c2c-kicker">Course2Career · 从校园经历，到岗位能力</p>',
        unsafe_allow_html=True,
    )
    st.title("把学过的课程，翻译成求职能力")
    st.markdown(
        '<p class="c2c-lead">导入课程，补充教育、项目与实习，再放入一份目标 JD。'
        "沿着证据路径，看清五维岗位适配度、独立硬门槛和下一步行动。</p>",
        unsafe_allow_html=True,
    )
    if analysis_page is not None:
        st.page_link(analysis_page, label="开始一次个人分析", icon="↗")
    st.caption("本地规则无需注册、不调用 AI。登录后可保存历史分析。")

    st.markdown("## 使用流程")
    st.markdown(
        dedent("""
        <div class="c2c-home-path" aria-label="材料、人工确认、规则报告三步流程">
          <div><strong>带来你的经历</strong>
          <p>课程、教育、项目、实习、成长条件与岗位原文。</p></div>
          <svg viewBox="0 0 48 56" aria-hidden="true">
          <path d="M2 12h12l16 32h16M34 35l12 9-12 9"
          fill="none" stroke="#173F35" stroke-width="3" /></svg>
          <div class="c2c-confirm"><strong>把理解确认下来</strong>
          <p>提取岗位技能，核对原文引用，确认或修正关键输入。</p></div>
          <svg viewBox="0 0 48 56" aria-hidden="true">
          <path d="M2 12h12l16 32h16M34 35l12 9-12 9"
          fill="none" stroke="#B7472B" stroke-width="3" /></svg>
          <div><strong>读懂判断与下一步</strong>
          <p>规则计算五维评分、独立门槛、材料来源与学习任务。</p></div>
        </div>
        """),
        unsafe_allow_html=True,
    )
    st.markdown("## 每个结论，都能回到材料")
    st.write(
        "AI 辅助理解 JD，也可使用本地规则。"
        "课程映射、技能迁移、五维评分、门槛与学习路线由 Python 规则完成。"
        "分析前由你核对，分析后可回看逐项加减分账本并导出。"
    )
    st.markdown(
        dedent("""
        <div class="c2c-home-evidence">
          <span>合成示例 · 在个人分析页可运行</span>
          <h3>课程支持 SQL，毕业年份仍可能不满足。</h3>
          <p>“SQL数据库原理”能提供技能材料；2027 届不满足只接受 2026 届的岗位。
          技能支撑与硬门槛分别呈现，不把一个判断藏进另一个分数。</p>
        </div>
        """),
        unsafe_allow_html=True,
    )
    st.markdown("### 先体验，再放入自己的材料")
    st.write(
        "进入个人分析，展开“三个求职方向合成演示”，"
        "先看输入，再运行本地规则。示例独立运行，不覆盖正在填写的资料。"
    )
    st.caption(
        "结果用于学习决策，不预测录用概率。材料支撑不等于熟练掌握；"
        "自述与人工确认不等于外部验证。真实用户效果与人工标注校准尚未完成。"
    )
