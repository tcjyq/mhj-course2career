from io import BytesIO
from pathlib import Path

import pandas as pd
from streamlit.testing.v1 import AppTest

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


def test_app_initial_page_is_product_home() -> None:
    app = AppTest.from_file("app.py").run()

    assert not app.exception
    assert app.title[0].value == "把学过的课程，翻译成求职能力"
    assert any("使用流程" in block.value for block in app.markdown)
    assert len(app.file_uploader) == 0


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
        button for button in app.button if button.label == "生成匹配报告"
    ).click().run()
    assert not app.exception
    assert any(metric.label == "综合匹配分" for metric in app.metric)


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
