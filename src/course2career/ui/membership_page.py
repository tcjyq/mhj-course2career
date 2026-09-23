import pandas as pd
import streamlit as st

from course2career.byok_mode import BYOKModeService
from course2career.permissions import Plan, Principal, Role
from course2career.ui.byok_mode_controls import render_byok_mode_controls

PLAN_LABELS = {
    Plan.FREE: "Free",
    Plan.PRO: "Pro",
    Plan.DEVELOPER: "Developer",
    Plan.ADMIN: "Admin",
}


def render_membership_page(
    principal: Principal,
    byok_mode_service: BYOKModeService | None = None,
    developer_page: object | None = None,
) -> None:
    st.title("会员方案")
    st.caption("Free / Pro 为套餐演示；开发者模式可独立免费启用。")

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
                },
                {
                    "方案": "Pro",
                    "平台AI": "20次/天",
                    "历史记录": "支持",
                    "高级报告": "支持",
                },
            ]
        ),
        width="stretch",
        hide_index=True,
    )

    st.markdown("## 开发者模式")
    enabled = render_byok_mode_controls(
        principal, byok_mode_service, key_prefix="membership"
    )
    if developer_page is not None and principal.role != Role.GUEST:
        st.page_link(
            developer_page,
            label="管理 API Key" if enabled else "前往开发者模式",
        )

    st.markdown("## 套餐演示")
    if principal.role == Role.GUEST:
        st.info("登录后可体验 Free / Pro 套餐演示。")
        return

    with st.form("membership_demo_form"):
        target_plan = st.selectbox(
            "目标方案",
            [Plan.FREE, Plan.PRO],
            format_func=lambda plan: PLAN_LABELS[plan],
        )
        submitted = st.form_submit_button("演示升级", type="primary")
    if submitted:
        if target_plan == principal.plan:
            st.info("你当前已经是该方案。")
        else:
            st.success(f"{PLAN_LABELS[target_plan]} 界面演示完成，当前套餐未改变。")
    st.caption("此演示不创建订单、不扣款，也不启用开发者模式。")
