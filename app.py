from uuid import uuid4

import streamlit as st

from course2career.access_services import (
    AdminDashboardService,
    AIUsageService,
    AnalysisRecordService,
)
from course2career.admin_dashboard import render_admin_dashboard
from course2career.api_key_service import APIKeyService
from course2career.auth_service import (
    AdminBootstrapError,
    AuthService,
    InvalidSessionError,
)
from course2career.config import load_settings
from course2career.key_encryption import (
    APIKeyCipher,
    KeyEncryptionConfigurationError,
)
from course2career.membership_service import MembershipService
from course2career.permissions import Plan, Principal, Role
from course2career.product_repository import SQLiteProductRepository
from course2career.provider_factory import LLMProviderFactory
from course2career.ui.analysis_page import render_analysis_page
from course2career.ui.auth_page import render_auth_page
from course2career.ui.developer_page import render_developer_page
from course2career.ui.home_page import render_home_page
from course2career.ui.membership_page import render_membership_page
from course2career.ui.quota_page import render_quota_page
from course2career.ui.styles import apply_product_styles

st.set_page_config(
    page_title="Course2Career",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_product_styles()


@st.cache_resource
def get_repository(
    database_path: str,
    schema_revision: int,
) -> SQLiteProductRepository:
    return SQLiteProductRepository(database_path)


settings = load_settings()
repository = get_repository(settings.database_path, schema_revision=2)
auth_service = AuthService(repository)
admin_username = getattr(settings, "admin_username", None)
admin_password = getattr(settings, "admin_password", None)
admin_password_hash = getattr(settings, "admin_password_hash", None)
if admin_username or admin_password or admin_password_hash:
    if not admin_username or bool(admin_password) == bool(admin_password_hash):
        st.error("管理员初始化配置无效，请检查环境变量。")
        st.stop()
    try:
        auth_service.ensure_bootstrap_admin(
            admin_username,
            admin_password,
            password_hash=admin_password_hash,
        )
    except AdminBootstrapError as exc:
        st.error(f"管理员初始化失败：{exc}")
        st.stop()
usage_service = AIUsageService(repository)
record_service = AnalysisRecordService(repository)
dashboard_service = AdminDashboardService(repository)
membership_service = MembershipService(repository)

api_key_service = None
key_configuration_error = None
if settings.key_encryption_key:
    try:
        api_key_service = APIKeyService(
            repository,
            APIKeyCipher.from_base64_key(settings.key_encryption_key),
        )
    except KeyEncryptionConfigurationError as exc:
        key_configuration_error = str(exc)
provider_factory = LLMProviderFactory(settings, api_key_service)

if "principal" not in st.session_state:
    st.session_state.principal = Principal()
if "guest_session_id" not in st.session_state:
    st.session_state.guest_session_id = str(uuid4())

principal: Principal = st.session_state.principal
if principal.role != Role.GUEST:
    try:
        principal = auth_service.refresh_principal(principal)
        st.session_state.principal = principal
    except InvalidSessionError:
        for state_key in (
            "principal",
            "job_analysis",
            "analysis_report",
            "legacy_analysis_report",
        ):
            st.session_state.pop(state_key, None)
        st.warning("登录状态已失效，请重新登录。")
        st.rerun()
role_labels = {
    Role.GUEST: "游客",
    Role.USER: "普通用户",
    Role.DEVELOPER: "开发者",
    Role.ADMIN: "管理员",
}
plan_labels = {
    Plan.FREE: "Free",
    Plan.PRO: "Pro",
    Plan.DEVELOPER: "Developer",
    Plan.ADMIN: "Admin",
}

with st.sidebar:
    st.markdown("## Course2Career")
    st.caption("大学生岗位适配度评估")
    st.markdown("---")
    identity = principal.username or "未登录"
    st.write(identity)
    st.caption(f"{role_labels[principal.role]} · {plan_labels[principal.plan]}")
    if principal.role == Role.GUEST:
        st.caption("可直接体验个人分析，登录后保存记录。")
    elif st.button("退出登录", width="stretch"):
        for state_key in (
            "principal",
            "job_analysis",
            "analysis_report",
            "legacy_analysis_report",
        ):
            st.session_state.pop(state_key, None)
        st.rerun()

home_page = st.Page(
    render_home_page,
    title="首页",
    url_path="home",
    default=True,
)
login_page = st.Page(
    lambda: render_auth_page(principal, auth_service),
    title="登录",
    url_path="login",
)
analysis_page = st.Page(
    lambda: render_analysis_page(
        principal,
        settings,
        provider_factory,
        usage_service,
        record_service,
        api_key_service,
        st.session_state.guest_session_id,
    ),
    title="个人分析",
    url_path="analysis",
)
quota_page = st.Page(
    lambda: render_quota_page(
        principal,
        usage_service,
        st.session_state.guest_session_id,
    ),
    title="AI额度",
    url_path="quota",
)
membership_page = st.Page(
    lambda: render_membership_page(principal),
    title="会员升级",
    url_path="membership",
)
developer_page = st.Page(
    lambda: render_developer_page(
        principal,
        api_key_service,
        key_configuration_error,
    ),
    title="开发者API Key",
    url_path="developer",
)

navigation = {
    "开始": [home_page, login_page],
    "工作台": [analysis_page, quota_page],
    "账户": [membership_page, developer_page],
}
if principal.role == Role.ADMIN and principal.plan == Plan.ADMIN:
    admin_page = st.Page(
        lambda: render_admin_dashboard(
            principal,
            dashboard_service,
            membership_service,
        ),
        title="管理员Dashboard",
        url_path="admin",
    )
    navigation["管理"] = [admin_page]

st.navigation(navigation, position="sidebar").run()
