from io import BytesIO
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

from course2career.auth_service import AuthService
from course2career.permissions import Plan, Role
from course2career.product_repository import SQLiteProductRepository


def _analysis_app(
    tmp_path: Path,
    *,
    developer: bool = False,
) -> AppTest:
    database_path = (tmp_path / "analysis.db").as_posix()
    principal_source = (
        """
principal = Principal(
    role=Role.DEVELOPER,
    plan=Plan.DEVELOPER,
    user_id="developer-test",
    username="developer",
)
key_service = APIKeyService(repository, APIKeyCipher(bytes(range(32))))
"""
        if developer
        else """
principal = Principal()
key_service = None
"""
    )
    return AppTest.from_string(
        f"""
from course2career.access_services import AIUsageService, AnalysisRecordService
from course2career.api_key_service import APIKeyService
from course2career.config import Settings
from course2career.key_encryption import APIKeyCipher
from course2career.permissions import Plan, Principal, Role
from course2career.product_repository import SQLiteProductRepository
from course2career.provider_factory import LLMProviderFactory
from course2career.ui.analysis_page import render_analysis_page

repository = SQLiteProductRepository(r"{database_path}")
settings = Settings()
{principal_source}
render_analysis_page(
    principal,
    settings,
    LLMProviderFactory(settings, key_service),
    AIUsageService(repository),
    AnalysisRecordService(repository),
    key_service,
    "guest-test",
)
"""
    ).run()


def _course_excel() -> bytes:
    frame = pd.DataFrame(
        [
            {
                "课程名称": "数据库原理",
                "学分": 3,
                "成绩": 88,
                "课程类别": "专业必修",
                "自评掌握程度": 4,
            }
        ]
    )
    excel_file = BytesIO()
    frame.to_excel(excel_file, index=False, engine="openpyxl")
    return excel_file.getvalue()


def _history_analysis_app(
    tmp_path: Path,
    *,
    legacy: bool = False,
    duplicate_summary: bool = False,
) -> AppTest:
    database_path = (tmp_path / "history-analysis.db").as_posix()
    report_source = (
        """
report = AnalysisReport(
    job_title="数据分析实习生",
    overall_score=72,
    strengths=["SQL"],
    gaps=["Docker"],
    limitations=["旧版报告"],
)
"""
        if legacy
        else """
report = AdaptabilityReport(
    job_title="AI应用开发实习生",
    overall_score=68,
    eligibility=EligibilityResult(status=EligibilityStatus.PASS),
    dimension_scores=DimensionScores(
        technical=65,
        education=75,
        project=70,
        internship=60,
        potential=80,
    ),
    data_completeness=85,
    confidence="中等",
    strengths=["Python基础"],
    gaps=["RAG项目"],
    limitations=["不代表录用概率"],
)
"""
    )
    return AppTest.from_string(
        f"""
from course2career.access_services import AIUsageService, AnalysisRecordService
from course2career.config import Settings
from course2career.models import (
    AdaptabilityReport,
    AnalysisReport,
    DimensionScores,
    EligibilityResult,
    EligibilityStatus,
)
from course2career.permissions import Plan, Principal, Role
from course2career.product_repository import SQLiteProductRepository
from course2career.provider_factory import LLMProviderFactory
from course2career.ui.analysis_page import render_analysis_page
from course2career.user_repository import StoredUser
import sqlite3

repository = SQLiteProductRepository(r"{database_path}")
if repository.find_by_id("history-user") is None:
    repository.add(StoredUser(
        id="history-user",
        username="history-user",
        username_normalized="history-user",
        password_hash="not-used",
        role=Role.USER,
        plan=Plan.FREE,
        created_time="2026-08-03T00:00:00+00:00",
    ))
{report_source}
if not repository.list_analyses("history-user"):
    repository.add_analysis("history-user", report)
if {duplicate_summary!r} and len(repository.list_analyses("history-user")) < 2:
    repository.add_analysis("history-user", report)
    with sqlite3.connect(r"{database_path}") as connection:
        connection.execute(
            "UPDATE analysis_records SET created_time = ? WHERE user_id = ?",
            ("2026-08-03T08:00:00+00:00", "history-user"),
        )
principal = Principal(
    role=Role.USER,
    plan=Plan.FREE,
    user_id="history-user",
    username="history-user",
)
settings = Settings()
render_analysis_page(
    principal,
    settings,
    LLMProviderFactory(settings),
    AIUsageService(repository),
    AnalysisRecordService(repository),
    None,
    "guest-test",
)
"""
    ).run()


def test_app_initial_page_is_product_home() -> None:
    app = AppTest.from_file("app.py").run()

    assert not app.exception
    assert app.title[0].value == "把学过的课程，翻译成求职能力"
    assert any("使用流程" in block.value for block in app.markdown)
    assert any("五维岗位适配度" in block.value for block in app.markdown)
    assert len(app.file_uploader) == 0


def test_app_starts_during_legacy_settings_deployment_window() -> None:
    app_path = Path("app.py").resolve().as_posix()
    app = AppTest.from_string(
        f"""
import course2career.config

class LegacySettings:
    openai_api_key = None
    openai_model = "test-openai-model"
    deepseek_api_key = None
    deepseek_model = "deepseek-v4-flash"
    openai_timeout_seconds = 30.0
    database_path = "instance/legacy-settings-test.db"
    key_encryption_key = None

original_load_settings = course2career.config.load_settings
try:
    course2career.config.load_settings = lambda: LegacySettings()
    exec(compile(open(r"{app_path}", encoding="utf-8").read(), r"{app_path}", "exec"))
finally:
    course2career.config.load_settings = original_load_settings
"""
    ).run()

    assert not app.exception
    assert app.title[0].value == "把学过的课程，翻译成求职能力"


def test_app_bootstraps_owner_admin_from_environment(
    tmp_path: Path,
    monkeypatch,
) -> None:
    database_path = tmp_path / "admin-bootstrap.db"
    monkeypatch.setenv("COURSE2CAREER_DATABASE_PATH", str(database_path))
    monkeypatch.setenv("ADMIN_USERNAME", "owner_admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "unique-admin-pass-123")
    monkeypatch.delenv("ADMIN_PASSWORD_HASH", raising=False)

    app = AppTest.from_file("app.py").run()

    assert not app.exception
    principal = AuthService(SQLiteProductRepository(database_path)).authenticate(
        "owner_admin",
        "unique-admin-pass-123",
    )
    assert principal.role == Role.ADMIN
    assert principal.plan == Plan.ADMIN


def test_login_page_has_login_and_registration_forms(tmp_path: Path) -> None:
    repository = SQLiteProductRepository(tmp_path / "auth.db")
    app = AppTest.from_string(
        f"""
from course2career.auth_service import AuthService
from course2career.permissions import Principal
from course2career.product_repository import SQLiteProductRepository
from course2career.ui.auth_page import render_auth_page

repository = SQLiteProductRepository(r"{repository.database_path.as_posix()}")
render_auth_page(Principal(), AuthService(repository))
"""
    ).run()

    assert not app.exception
    assert app.title[0].value == "登录与账户"
    assert {button.label for button in app.button} >= {"登录", "注册"}


def test_analysis_page_upload_valid_excel_shows_course_preview(
    tmp_path: Path,
) -> None:
    app = _analysis_app(tmp_path)

    app.file_uploader[0].upload(
        "courses.xlsx",
        _course_excel(),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ).run()

    assert not app.exception
    assert any(message.value == "成功导入 1 门课程。" for message in app.success)
    assert app.dataframe[0].value.iloc[0]["课程名称"] == "数据库原理"


def test_analysis_page_upload_invalid_excel_shows_readable_error(
    tmp_path: Path,
) -> None:
    app = _analysis_app(tmp_path)

    app.file_uploader[0].upload(
        "courses.xlsx",
        b"not an xlsx file",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ).run()

    assert not app.exception
    assert "无法读取课程文件" in app.error[0].value


def test_analysis_page_runs_local_flow(tmp_path: Path) -> None:
    app = _analysis_app(tmp_path)
    app.file_uploader[0].upload(
        "courses.xlsx",
        _course_excel(),
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    app.text_area[0].set_value(
        "数据分析实习生\n核心要求：熟练掌握 SQL。Power BI 项目经验加分。"
    )

    next(
        button for button in app.button if button.label == "提取岗位技能"
    ).click().run()

    assert not app.exception
    assert any("已提取" in message.value for message in app.success)
    next(
        button for button in app.button if button.label == "生成岗位适配度报告"
    ).click().run()
    assert not app.exception
    assert any(metric.label == "岗位适配度" for metric in app.metric)
    assert any("为什么是这个分数" in block.value for block in app.markdown)


def test_analysis_page_reopens_current_saved_report(tmp_path: Path) -> None:
    app = _history_analysis_app(tmp_path)

    next(
        button for button in app.button if button.label == "重新打开这份报告"
    ).click().run()

    assert not app.exception
    assert any(metric.label == "岗位适配度" for metric in app.metric)
    assert any(metric.value == "68.0/100" for metric in app.metric)


def test_analysis_page_reopens_legacy_saved_report_without_crashing(
    tmp_path: Path,
) -> None:
    app = _history_analysis_app(tmp_path, legacy=True)

    next(
        button for button in app.button if button.label == "重新打开这份报告"
    ).click().run()

    assert not app.exception
    assert any("旧版技能匹配报告" in block.value for block in app.markdown)


def test_analysis_page_keeps_history_records_with_identical_summaries(
    tmp_path: Path,
) -> None:
    app = _history_analysis_app(tmp_path, duplicate_summary=True)

    history_selector = next(
        selectbox
        for selectbox in app.selectbox
        if selectbox.label == "选择一份历史报告"
    )

    assert len(history_selector.options) == 2


def test_developer_analysis_and_key_pages_are_available(tmp_path: Path) -> None:
    database_path = (tmp_path / "developer.db").as_posix()
    analysis_app = _analysis_app(tmp_path, developer=True)
    key_app = AppTest.from_string(
        f"""
from course2career.api_key_service import APIKeyService
from course2career.key_encryption import APIKeyCipher
from course2career.permissions import Plan, Principal, Role
from course2career.product_repository import SQLiteProductRepository
from course2career.ui.developer_page import render_developer_page

repository = SQLiteProductRepository(r"{database_path}")
developer = Principal(
    role=Role.DEVELOPER,
    plan=Plan.DEVELOPER,
    user_id="developer-test",
    username="developer",
)
render_developer_page(
    developer,
    APIKeyService(repository, APIKeyCipher(bytes(range(32)))),
    None,
)
"""
    ).run()

    assert not analysis_app.exception
    assert "开发者API Key" in analysis_app.radio[0].options
    assert not key_app.exception
    assert key_app.title[0].value == "开发者API Key"


def test_quota_and_membership_pages_render(tmp_path: Path) -> None:
    database_path = (tmp_path / "quota.db").as_posix()
    quota_app = AppTest.from_string(
        f"""
from course2career.access_services import AIUsageService
from course2career.permissions import Principal
from course2career.product_repository import SQLiteProductRepository
from course2career.ui.quota_page import render_quota_page

repository = SQLiteProductRepository(r"{database_path}")
render_quota_page(Principal(), AIUsageService(repository), "guest-test")
"""
    ).run()
    membership_app = AppTest.from_string(
        """
from course2career.permissions import Principal
from course2career.ui.membership_page import render_membership_page

render_membership_page(Principal())
"""
    ).run()

    assert not quota_app.exception
    assert {metric.label for metric in quota_app.metric} >= {
        "今日已用",
        "每日额度",
        "今日剩余",
    }
    assert not membership_app.exception
    assert membership_app.title[0].value == "会员方案"


def test_admin_dashboard_renders_metrics(tmp_path: Path) -> None:
    database_path = (tmp_path / "admin.db").as_posix()
    app = AppTest.from_string(
        f"""
from course2career.access_services import AdminDashboardService
from course2career.admin_dashboard import render_admin_dashboard
from course2career.membership_service import MembershipService
from course2career.permissions import Plan, Principal, Role
from course2career.product_repository import SQLiteProductRepository

repository = SQLiteProductRepository(r"{database_path}")
admin = Principal(
    role=Role.ADMIN,
    plan=Plan.ADMIN,
    user_id="admin-test",
    username="admin",
)
render_admin_dashboard(
    admin,
    AdminDashboardService(repository),
    MembershipService(repository),
)
"""
    ).run()

    assert not app.exception
    assert {
        "用户数量",
        "今日分析次数",
        "AI调用次数",
        "Token消耗",
        "预计费用",
    }.issubset({metric.label for metric in app.metric})


def test_admin_dashboard_rejects_normal_user_at_page_boundary(tmp_path: Path) -> None:
    database_path = (tmp_path / "normal-user-admin-page.db").as_posix()
    app = AppTest.from_string(
        f"""
from course2career.access_services import AdminDashboardService
from course2career.admin_dashboard import render_admin_dashboard
from course2career.membership_service import MembershipService
from course2career.permissions import Plan, Principal, Role
from course2career.product_repository import SQLiteProductRepository

repository = SQLiteProductRepository(r"{database_path}")
normal_user = Principal(
    role=Role.USER,
    plan=Plan.FREE,
    user_id="user-test",
    username="student",
)
render_admin_dashboard(
    normal_user,
    AdminDashboardService(repository),
    MembershipService(repository),
)
"""
    ).run()

    assert app.exception
    assert app.exception[0].message == "当前用户没有执行此操作的权限。"
    assert any("PermissionDeniedError" in line for line in app.exception[0].stack_trace)
