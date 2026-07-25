import streamlit as st

from course2career.access_services import AIUsageService
from course2career.permissions import Plan, Principal, Role

PLAN_LABELS = {
    Plan.FREE: "Free",
    Plan.PRO: "Pro",
    Plan.DEVELOPER: "Developer",
    Plan.ADMIN: "Admin",
}


def render_quota_page(
    principal: Principal,
    usage_service: AIUsageService,
    guest_session_id: str,
) -> None:
    st.title("AI额度")
    st.caption("额度按东八区自然日统计，本地规则分析不消耗AI次数。")

    status = usage_service.get_quota_status(
        principal,
        "system",
        guest_session_id=guest_session_id,
    )
    limit_text = "不限" if status.limit is None else str(status.limit)
    remaining_text = "不限" if status.remaining is None else str(status.remaining)
    used_column, limit_column, remaining_column = st.columns(3)
    used_column.metric("今日已用", status.used)
    limit_column.metric("每日额度", limit_text)
    remaining_column.metric("今日剩余", remaining_text)

    if status.limit:
        st.progress(
            min(status.used / status.limit, 1.0),
            text=f"已使用 {status.used}/{status.limit} 次",
        )

    with st.container(border=True):
        st.markdown(f"### 当前方案：{PLAN_LABELS[principal.plan]}")
        if principal.role == Role.GUEST:
            st.write("游客拥有2次每日体验额度。登录Free账户后每日可使用5次。")
        elif principal.plan == Plan.FREE:
            st.write("Free账户每日5次平台AI调用。")
        elif principal.plan in {Plan.PRO, Plan.DEVELOPER}:
            st.write("当前套餐每日20次平台AI调用。")
        else:
            st.write("管理员平台AI调用不受每日次数限制。")

    if principal.plan in {Plan.DEVELOPER, Plan.ADMIN}:
        with st.container(border=True):
            st.markdown("### 自带API Key")
            st.write("使用自己的API Key不消耗平台每日额度，费用由对应供应商计费。")
