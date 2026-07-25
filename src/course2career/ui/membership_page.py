import pandas as pd
import streamlit as st

from course2career.permissions import Plan, Principal, Role

PLAN_LABELS = {
    Plan.FREE: "Free",
    Plan.PRO: "Pro",
    Plan.DEVELOPER: "Developer",
    Plan.ADMIN: "Admin",
}


def render_membership_page(principal: Principal) -> None:
    st.title("会员方案")
    st.caption("当前为产品演示页，不会创建订单、扣款或改变真实套餐。")

    current_plan = (
        "游客" if principal.role == Role.GUEST else PLAN_LABELS[principal.plan]
    )
    st.markdown(f"### 当前状态：{current_plan}")
    st.dataframe(
        pd.DataFrame(
            [
                {
                    "方案": "Free",
                    "平台AI": "5次/天",
                    "历史记录": "支持",
                    "高级报告": "—",
                    "自带Key": "—",
                },
                {
                    "方案": "Pro",
                    "平台AI": "20次/天",
                    "历史记录": "支持",
                    "高级报告": "支持",
                    "自带Key": "—",
                },
                {
                    "方案": "Developer",
                    "平台AI": "20次/天",
                    "历史记录": "支持",
                    "高级报告": "支持",
                    "自带Key": "支持",
                },
                {
                    "方案": "Admin",
                    "平台AI": "不限",
                    "历史记录": "支持",
                    "高级报告": "支持",
                    "自带Key": "支持",
                },
            ]
        ),
        width="stretch",
        hide_index=True,
    )

    st.markdown("## 升级演示")
    if principal.role == Role.GUEST:
        st.info("请先在登录页面创建账户，再体验升级流程。")
        return

    with st.form("membership_demo_form"):
        target_plan = st.selectbox(
            "目标方案",
            [Plan.FREE, Plan.PRO, Plan.DEVELOPER],
            format_func=lambda plan: PLAN_LABELS[plan],
        )
        submitted = st.form_submit_button("演示升级", type="primary")
    if submitted:
        if target_plan == principal.plan:
            st.info("你当前已经是该方案。")
        else:
            st.success(
                f"演示完成：正式支付接入后，这里会创建"
                f"{PLAN_LABELS[target_plan]}升级订单。当前套餐未改变。"
            )
    st.caption("Admin不是可购买方案，只能通过受信任的管理流程授予。")
