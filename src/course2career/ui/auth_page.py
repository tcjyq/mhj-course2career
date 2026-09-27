from uuid import uuid4

import streamlit as st

from course2career.auth_service import (
    AuthService,
    InvalidCredentialsError,
)
from course2career.emergency_fallback import REGISTRATION_MESSAGE
from course2career.permissions import Plan, Principal, Role

PLAN_LABELS = {
    Plan.FREE: "Free",
    Plan.PRO: "Pro",
    Plan.DEVELOPER: "Developer",
    Plan.ADMIN: "Admin",
}


def render_auth_page(
    principal: Principal,
    auth_service: AuthService,
) -> None:
    st.title("登录与账户")
    st.caption("登录后可保存分析记录，继续使用本地规则和已配置的自带 API Key。")

    if principal.role != Role.GUEST:
        with st.container(border=True):
            st.markdown(f"### {principal.username}")
            st.write(f"当前套餐：{PLAN_LABELS[principal.plan]}")
            st.write("账户已登录。可以从左侧进入个人分析、AI额度或开发者页面。")
        return

    with st.container(border=True):
        st.markdown("## 登录")
        with st.form("login_form"):
            login_username = st.text_input(
                "用户名",
                autocomplete="username",
            )
            login_password = st.text_input(
                "密码",
                type="password",
                autocomplete="current-password",
            )
            login_submitted = st.form_submit_button(
                "登录",
                type="primary",
                width="stretch",
            )
        if login_submitted:
            try:
                authenticated = auth_service.authenticate(
                    login_username,
                    login_password,
                    attempt_scope=st.session_state.guest_session_id,
                )
                previous = st.session_state.get("auth_session_token")
                if previous:
                    auth_service.revoke_session(previous)
                token = auth_service.create_session(authenticated)
                st.session_state.pending_auth_storage = {
                    "action": "set",
                    "nonce": uuid4().hex,
                    "token": token,
                }
                st.session_state.auth_session_token = token
                st.session_state.principal = authenticated
                st.rerun()
            except InvalidCredentialsError as exc:
                st.error(str(exc))

    st.info(REGISTRATION_MESSAGE)
