import pandas as pd
import streamlit as st

from course2career.access_services import AdminDashboardService
from course2career.membership_service import (
    MembershipChangeError,
    MembershipService,
    UserNotFoundError,
)
from course2career.permissions import (
    PermissionDeniedError,
    Plan,
    Principal,
)

PLAN_LABELS = {
    Plan.FREE: "Free",
    Plan.PRO: "Pro",
    Plan.DEVELOPER: "Developer",
    Plan.ADMIN: "Admin",
}


def render_admin_dashboard(
    principal: Principal,
    dashboard_service: AdminDashboardService,
    membership_service: MembershipService,
) -> None:
    """渲染轻量管理员概况和会员管理页面。"""

    overview = dashboard_service.get_overview(principal)
    users = dashboard_service.list_users(principal)

    st.title("管理员 Dashboard")
    st.caption("系统概况、用户套餐和AI成本汇总")

    st.markdown("## 系统概况")
    user_column, analysis_column, call_column, token_column = st.columns(4)
    user_column.metric("用户数量", f"{overview.user_count:,}")
    analysis_column.metric("今日分析次数", f"{overview.today_analysis_count:,}")
    call_column.metric("AI调用次数", f"{overview.ai_call_count:,}")
    token_column.metric("Token消耗", f"{overview.total_tokens:,}")

    st.markdown("## AI成本")
    st.metric(
        "预计费用",
        f"${overview.estimated_cost:,.4f}",
        help="累计api_usage.cost，仅用于运营估算，不作为账单依据。",
    )

    st.markdown("## 用户管理")
    if not users:
        st.info("当前还没有可管理的注册用户。")
        return

    users_by_id = {user.id: user for user in users}
    selected_user_id = st.selectbox(
        "选择用户",
        options=list(users_by_id),
        format_func=lambda user_id: (
            f"{users_by_id[user_id].username} · "
            f"{PLAN_LABELS[Plan(users_by_id[user_id].plan)]}"
        ),
    )
    selected_user = users_by_id[selected_user_id]
    current_plan = Plan(selected_user.plan)
    plans = list(Plan)
    with st.form("admin_membership_form"):
        target_plan = st.selectbox(
            "套餐",
            options=plans,
            index=plans.index(current_plan),
            format_func=lambda plan: PLAN_LABELS[plan],
        )
        submitted = st.form_submit_button("保存权限")

    if submitted:
        try:
            membership_service.change_plan(
                principal,
                selected_user_id,
                target_plan,
            )
            st.success("用户权限已更新。")
            users = dashboard_service.list_users(principal)
        except (
            MembershipChangeError,
            PermissionDeniedError,
            UserNotFoundError,
        ) as exc:
            st.error(str(exc))

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "用户名": user.username,
                    "角色": user.role,
                    "套餐": PLAN_LABELS[Plan(user.plan)],
                    "注册时间": user.created_time,
                }
                for user in users
            ]
        ),
        width="stretch",
        hide_index=True,
    )
