# Deployment refresh marker: 2026-09-29 post-PR4
from urllib.parse import urlsplit
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
from course2career.byok_mode import BYOKModeService
from course2career.config import load_settings
from course2career.database_backend import (
    DatabaseConfigurationError,
    DatabaseUnavailableError,
    log_database_startup_failure,
)
from course2career.key_encryption import (
    APIKeyCipher,
    KeyEncryptionConfigurationError,
)
from course2career.membership_service import MembershipService
from course2career.model_catalog import DeepSeekModelCatalog
from course2career.model_discovery import ModelCatalogService
from course2career.permissions import Plan, Principal, Role
from course2career.postgres_repository import PostgresProductRepository
from course2career.product_repository import SQLiteProductRepository
from course2career.provider_factory import LLMProviderFactory
from course2career.provider_profile import ProviderProfileService
from course2career.ui.analysis_page import render_analysis_page
from course2career.ui.auth_page import render_auth_page
from course2career.ui.browser_auth import log_restore_state, read_browser_storage
from course2career.ui.developer_page import render_developer_page
from course2career.ui.home_page import render_home_page
from course2career.ui.identity_state import clear_identity_state
from course2career.ui.installation import read_installation
from course2career.ui.membership_page import render_membership_page
from course2career.ui.quota_page import render_quota_page
from course2career.ui.styles import apply_product_styles

st.set_page_config(
    page_title="Course2Career",
    layout="wide",
    initial_sidebar_state="expanded",
)
apply_product_styles()


def show_auth_restore_pending(message: str = "正在全力加载…") -> None:
    def render_pending() -> None:
        st.info(message)

    pages = [
        st.Page(
            render_pending,
            title=title,
            url_path=path,
            default=path == "home",
        )
        for title, path in (
            ("首页", "home"),
            ("登录", "login"),
            ("个人分析", "analysis"),
            ("AI额度", "quota"),
            ("会员方案", "membership"),
            ("我的 AI Provider", "developer"),
            ("管理员Dashboard", "admin"),
        )
    ]
    st.navigation(pages, position="hidden").run()
    st.stop()


@st.cache_resource
def get_repository(
    database_path: str,
    schema_revision: int,
    database_url: str | None = None,
    production_mode: bool = False,
) -> SQLiteProductRepository:
    if production_mode:
        if not database_url:
            raise DatabaseConfigurationError("生产模式缺少持久数据库。")
        return PostgresProductRepository(database_url, require_verified_tls=True)
    if database_url:
        raise DatabaseConfigurationError("本地模式不能使用生产 DATABASE_URL。")
    return SQLiteProductRepository(database_path)


@st.cache_resource
def get_deepseek_model_catalog(
    timeout_seconds: float,
    cache_seconds: int,
    stale_seconds: int,
) -> DeepSeekModelCatalog:
    return DeepSeekModelCatalog(
        timeout_seconds=timeout_seconds,
        cache_seconds=cache_seconds,
        stale_seconds=stale_seconds,
    )


settings = load_settings()
try:
    repository = get_repository(
        settings.database_path,
        schema_revision=8,
        database_url=getattr(settings, "database_url", None),
        production_mode=getattr(settings, "production_mode", False),
    )
except Exception as exc:
    log_database_startup_failure(exc)
    st.error("开发者模式暂时不可用：持久数据库连接或配置失败。")
    st.stop()
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
usage_service = AIUsageService(repository, settings)
record_service = AnalysisRecordService(repository)
dashboard_service = AdminDashboardService(repository)
membership_service = MembershipService(repository)
byok_mode_service = BYOKModeService(repository)
profile_service = ProviderProfileService(repository)

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
catalog_service = None
if api_key_service is not None:
    if "model_catalog_service" not in st.session_state:
        st.session_state.model_catalog_service = ModelCatalogService(api_key_service)
    catalog_service = st.session_state.model_catalog_service
    catalog_service.api_keys = api_key_service
model_catalog = get_deepseek_model_catalog(
    settings.openai_timeout_seconds,
    getattr(settings, "deepseek_model_cache_seconds", 1800),
    getattr(settings, "deepseek_model_stale_seconds", 86400),
)
provider_factory = LLMProviderFactory(settings, api_key_service)
provider_factory.model_catalog = model_catalog
installation = read_installation()

if not st.session_state.get("auth_initial_path_captured"):
    context_url = st.context.url
    st.session_state.auth_requested_path = (
        urlsplit(context_url).path.strip("/") if isinstance(context_url, str) else ""
    )
    st.session_state.auth_initial_path_captured = True
if "auth_storage_nonce" not in st.session_state:
    st.session_state.auth_storage_nonce = uuid4().hex
pending_storage = st.session_state.get("pending_auth_storage")
storage_action = pending_storage["action"] if pending_storage else "read"
storage_nonce = (
    pending_storage["nonce"] if pending_storage else st.session_state.auth_storage_nonce
)
try:
    browser_storage = read_browser_storage(
        action=storage_action,
        nonce=storage_nonce,
        token=pending_storage.get("token") if pending_storage else None,
    )
except Exception:
    st.error("页面暂时无法加载，请刷新重试。")
    st.stop()
if pending_storage and browser_storage.phase != "PENDING":
    st.session_state.pop("pending_auth_storage", None)
    if storage_action == "set" and (
        not browser_storage.ok or browser_storage.token != pending_storage["token"]
    ):
        st.warning("暂时无法保持登录，刷新后可能需要重新登录。")
elif pending_storage and storage_action == "set":
    show_auth_restore_pending("正在全力加载…")
if "principal" not in st.session_state:
    if pending_storage and storage_action == "clear":
        log_restore_state(
            browser_storage, server_session_found=False, restore_result="guest"
        )
        st.session_state.principal = Principal()
    elif browser_storage.phase == "PENDING":
        log_restore_state(
            browser_storage, server_session_found=False, restore_result="pending"
        )
        show_auth_restore_pending()
    elif browser_storage.phase == "TOKEN_PRESENT":
        try:
            restored = auth_service.restore_session(browser_storage.token)
        except DatabaseUnavailableError:
            st.error("开发者模式暂时不可用：持久数据库连接失败。")
            st.stop()
        if restored is None:
            log_restore_state(
                browser_storage, server_session_found=False, restore_result="guest"
            )
            st.session_state.pending_auth_storage = {
                "action": "clear",
                "nonce": uuid4().hex,
            }
            st.session_state.principal = Principal()
        else:
            log_restore_state(
                browser_storage,
                server_session_found=True,
                restore_result="authenticated",
            )
            st.session_state.auth_session_token = browser_storage.token
            st.session_state.principal = restored
    else:
        log_restore_state(
            browser_storage, server_session_found=False, restore_result="guest"
        )
        st.session_state.principal = Principal()
if "guest_session_id" not in st.session_state:
    st.session_state.guest_session_id = str(uuid4())

principal: Principal = st.session_state.principal
if principal.role != Role.GUEST:
    try:
        principal = auth_service.refresh_session(
            principal, st.session_state.get("auth_session_token")
        )
        st.session_state.principal = principal
    except InvalidSessionError:
        auth_service.revoke_session(st.session_state.get("auth_session_token"))
        clear_identity_state(st.session_state)
        st.session_state.pending_auth_storage = {
            "action": "clear",
            "nonce": uuid4().hex,
        }
        for state_key in (
            "principal",
            "auth_session_token",
        ):
            st.session_state.pop(state_key, None)
        st.warning("登录状态已失效，请重新登录。")
        st.rerun()
    except DatabaseUnavailableError:
        st.error("开发者模式暂时不可用：持久数据库连接失败。")
        st.stop()
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
        auth_service.revoke_session(st.session_state.get("auth_session_token"))
        clear_identity_state(st.session_state)
        st.session_state.pending_auth_storage = {
            "action": "clear",
            "nonce": uuid4().hex,
        }
        for state_key in (
            "principal",
            "auth_session_token",
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
    lambda: render_auth_page(principal, auth_service, settings, installation),
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
        profile_service,
        catalog_service,
        installation,
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
    lambda: render_membership_page(principal, byok_mode_service, developer_page),
    title="会员方案",
    url_path="membership",
)
developer_page = st.Page(
    lambda: render_developer_page(
        principal,
        api_key_service,
        key_configuration_error,
        profile_service,
        provider_factory,
        byok_mode_service,
        catalog_service,
    ),
    title="我的 AI Provider",
    url_path="developer",
)

account_pages = [membership_page, developer_page]

navigation = {
    "开始": [home_page, login_page],
    "工作台": [analysis_page, quota_page],
    "账户": account_pages,
}
if principal.role == Role.ADMIN and principal.plan == Plan.ADMIN:
    admin_page = st.Page(
        lambda: render_admin_dashboard(
            principal,
            dashboard_service,
            membership_service,
            settings=settings,
            model_catalog=model_catalog,
        ),
        title="管理员Dashboard",
        url_path="admin",
    )
    navigation["管理"] = [admin_page]

selected_page = st.navigation(navigation, position="sidebar")
current_page_path = selected_page.url_path
requested_path = st.session_state.pop("auth_requested_path", None)
identity_just_cleared = st.session_state.pop("identity_just_cleared", False)
if requested_path and requested_path != current_page_path and not identity_just_cleared:
    for page_group in navigation.values():
        matching_page = next(
            (page for page in page_group if page.url_path == requested_path), None
        )
        if matching_page is not None:
            st.switch_page(matching_page)
previous_page_path = st.session_state.get("_active_page_path")
page_slot = st.empty()
if identity_just_cleared:
    page_slot.empty()
    with page_slot.container():
        render_home_page()
    st.stop()
if previous_page_path is not None and previous_page_path != current_page_path:
    page_slot.empty()
    st.session_state._active_page_path = current_page_path
    st.rerun()
st.session_state._active_page_path = current_page_path
with page_slot.container():
    try:
        selected_page.run()
    except DatabaseUnavailableError:
        st.error("开发者模式暂时不可用：持久数据库连接失败。")
        st.stop()
