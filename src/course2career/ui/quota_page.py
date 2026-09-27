import streamlit as st

from course2career.access_services import AIUsageService
from course2career.emergency_fallback import SYSTEM_AI_MESSAGE
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
    st.info(SYSTEM_AI_MESSAGE)

    with st.container(border=True):
        st.markdown(f"### 当前方案：{PLAN_LABELS[principal.plan]}")
        st.write("平台 AI 暂停期间，本地规则与已配置的自带 API Key 仍可使用。")

    if (
        principal.byok_enabled
        or principal.plan in {Plan.DEVELOPER, Plan.ADMIN}
        or principal.role in {Role.DEVELOPER, Role.ADMIN}
    ):
        with st.container(border=True):
            st.markdown("### 自带API Key")
            st.write("使用自己的API Key不消耗平台每日额度，费用由对应供应商计费。")
