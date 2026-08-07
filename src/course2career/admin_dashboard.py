import pandas as pd
import streamlit as st

from course2career.access_services import AdminDashboardService
from course2career.config import Settings
from course2career.membership_service import (
    MembershipChangeError,
    MembershipService,
    UserNotFoundError,
)
from course2career.model_catalog import (
    DeepSeekModelCatalog,
    ModelDiscoveryError,
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
    settings: Settings | None = None,
    model_catalog: DeepSeekModelCatalog | None = None,
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
        f"{overview.estimated_cost:,.4f}",
        help="所有供应商单价需使用同一币种；仅用于预算观察，不作为账单依据。",
    )

    if settings is not None and model_catalog is not None:
        _render_deepseek_model_status(settings, model_catalog)

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
    plans = (
        [Plan.ADMIN]
        if current_plan == Plan.ADMIN
        else [Plan.FREE, Plan.PRO, Plan.DEVELOPER]
    )
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


def _render_deepseek_model_status(
    settings: Settings,
    model_catalog: DeepSeekModelCatalog,
) -> None:
    st.markdown("## DeepSeek 模型状态")
    mode = getattr(settings, "deepseek_model_mode", "pinned")
    mode_label = "Auto-Safe 自动选择" if mode == "auto_safe" else "固定模型"
    st.write(f"**选择策略：** {mode_label}")
    st.write(f"**固定回退模型：** {settings.deepseek_model}")
    if mode == "auto_safe":
        preference = " → ".join(
            getattr(settings, "deepseek_model_preference", (settings.deepseek_model,))
        )
        st.write(f"**已验证优先顺序：** {preference}")

    if not settings.deepseek_api_key:
        st.info("未配置平台 DeepSeek API Key，无法读取模型目录。")
        return

    cached = model_catalog.peek(settings.deepseek_api_key)
    if cached is not None:
        freshness = "缓存已过期" if cached.stale else "缓存有效"
        st.caption(
            f"{freshness} · 最近刷新：{cached.fetched_at.isoformat()} · "
            f"目录模型：{'、'.join(cached.available_models)}"
        )
    else:
        st.caption("当前进程尚未读取 DeepSeek 模型目录。")

    if st.button("刷新 DeepSeek 模型目录", key="refresh_deepseek_models"):
        try:
            snapshot = model_catalog.get_models(
                settings.deepseek_api_key,
                force_refresh=True,
            )
        except ModelDiscoveryError as exc:
            st.error(str(exc))
        else:
            message = "模型目录已刷新：" + "、".join(snapshot.available_models)
            if snapshot.stale:
                st.warning("官方目录暂时不可用，当前继续使用最近一次有效缓存。")
            else:
                st.success(message)
