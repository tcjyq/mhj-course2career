import streamlit as st

from course2career.auth_service import (
    AuthService,
    InvalidCredentialsError,
    RegistrationError,
)
from course2career.permissions import Plan, Principal, Role

PLAN_LABELS = {
    Plan.FREE: "Free",
    Plan.PRO: "Pro",
    Plan.DEVELOPER: "Developer",
    Plan.ADMIN: "Admin",
}


def render_auth_page(principal: Principal, auth_service: AuthService) -> None:
    st.title("登录与账户")
    st.caption("登录后保存分析记录，并使用与你套餐对应的AI额度。")

    if principal.role != Role.GUEST:
        with st.container(border=True):
            st.markdown(f"### {principal.username}")
            st.write(f"当前套餐：{PLAN_LABELS[principal.plan]}")
            st.write("账户已登录。可以从左侧进入个人分析、AI额度或开发者页面。")
        return

    login_column, register_column = st.columns(2, gap="large")
    with login_column:
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
                st.session_state.principal = auth_service.authenticate(
                    login_username,
                    login_password,
                )
                st.rerun()
            except InvalidCredentialsError as exc:
                st.error(str(exc))

    with register_column:
        st.markdown("## 创建Free账户")
        with st.form("register_form"):
            register_username = st.text_input(
                "用户名",
                key="register_username",
                autocomplete="username",
                help="3到32个字符，可使用字母、数字、下划线和连字符。",
            )
            register_password = st.text_input(
                "密码",
                type="password",
                key="register_password",
                autocomplete="new-password",
                help="至少8个字符。",
            )
            register_submitted = st.form_submit_button(
                "注册",
                width="stretch",
            )
        if register_submitted:
            try:
                st.session_state.principal = auth_service.register(
                    register_username,
                    register_password,
                )
                st.rerun()
            except RegistrationError as exc:
                st.error(str(exc))
