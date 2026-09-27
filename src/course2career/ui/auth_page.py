from uuid import uuid4

import streamlit as st

from course2career.auth_service import (
    AuthService,
    InvalidCredentialsError,
    RegistrationError,
)
from course2career.config import Settings
from course2career.permissions import Plan, Principal, Role
from course2career.turnstile import TurnstileError, build_registration_verifier
from course2career.ui.installation import InstallationState
from course2career.ui.turnstile_widget import read_registration_challenge

PLAN_LABELS = {
    Plan.FREE: "Free",
    Plan.PRO: "Pro",
    Plan.DEVELOPER: "Developer",
    Plan.ADMIN: "Admin",
}


def render_auth_page(
    principal: Principal,
    auth_service: AuthService,
    settings: Settings | None = None,
    installation: InstallationState | None = None,
) -> None:
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

    with register_column:
        st.markdown("## 创建Free账户")
        if "registration_challenge_nonce" not in st.session_state:
            st.session_state.registration_challenge_nonce = uuid4().hex
        site_key = settings.turnstile_site_key if settings else None
        challenge_token = read_registration_challenge(
            site_key, nonce=st.session_state.registration_challenge_nonce
        )
        registration_ready = (
            installation is not None
            and installation.phase == "PRESENT"
            and challenge_token is not None
            and settings is not None
            and bool(settings.turnstile_secret_key)
        )
        if not site_key or not settings or not settings.turnstile_secret_key:
            st.caption("创建账户暂时不可用，仍可使用本地规则体验。")
        elif installation is None or installation.phase == "UNAVAILABLE":
            st.caption("暂时无法创建账户，请检查浏览器设置后刷新重试。")
        elif installation.phase == "PENDING" or challenge_token is None:
            st.caption("请稍候，完成页面验证后即可创建账户。")
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
                disabled=not registration_ready,
            )
        if register_submitted:
            try:
                registered = auth_service.register_public(
                    register_username,
                    register_password,
                    installation_id=installation.value if installation else None,
                    turnstile_token=challenge_token,
                    verifier=build_registration_verifier(settings),
                )
                previous = st.session_state.get("auth_session_token")
                if previous:
                    auth_service.revoke_session(previous)
                token = auth_service.create_session(registered)
                st.session_state.pending_auth_storage = {
                    "action": "set",
                    "nonce": uuid4().hex,
                    "token": token,
                }
                st.session_state.auth_session_token = token
                st.session_state.principal = registered
                st.rerun()
            except (RegistrationError, TurnstileError) as exc:
                st.session_state.registration_challenge_nonce = uuid4().hex
                st.error(str(exc))
