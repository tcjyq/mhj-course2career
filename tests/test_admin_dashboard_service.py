from datetime import UTC, datetime
from pathlib import Path

import pytest

from course2career.access_services import AdminDashboardService
from course2career.models import AnalysisReport
from course2career.permissions import (
    PermissionDeniedError,
    Plan,
    Principal,
    Role,
)
from course2career.product_repository import SQLiteProductRepository
from course2career.user_repository import StoredUser


@pytest.fixture
def repository(tmp_path: Path) -> SQLiteProductRepository:
    return SQLiteProductRepository(tmp_path / "test.db")


def _admin() -> Principal:
    return Principal(
        role=Role.ADMIN,
        plan=Plan.ADMIN,
        user_id="admin-1",
        username="admin",
    )


def test_admin_overview_aggregates_users_analysis_usage_and_cost(
    repository: SQLiteProductRepository,
) -> None:
    repository.add(
        StoredUser(
            id="user-1",
            username="student",
            username_normalized="student",
            password_hash="not-exposed",
            role=Role.USER,
            plan=Plan.FREE,
            created_time="2026-07-25T00:00:00+00:00",
        )
    )
    repository.add_analysis(
        "user-1",
        AnalysisReport(job_title="数据分析师", overall_score=75),
    )
    usage_id = repository.reserve_ai_call(
        user_id="user-1",
        guest_session_id=None,
        key_mode="system",
        model="test-model",
        provider="openai",
        daily_limit=5,
        created_time=datetime.now(UTC),
    )
    repository.complete_ai_call(
        usage_id,
        status="success",
        input_tokens=100,
        output_tokens=50,
        cost=0.004,
    )
    service = AdminDashboardService(repository)

    overview = service.get_overview(_admin())
    users = service.list_users(_admin())

    assert overview.user_count == 1
    assert overview.today_analysis_count == 1
    assert overview.ai_call_count == 1
    assert overview.total_tokens == 150
    assert overview.estimated_cost == pytest.approx(0.004)
    assert users[0].username == "student"
    assert not hasattr(users[0], "password_hash")


def test_admin_dashboard_rejects_non_admin(
    repository: SQLiteProductRepository,
) -> None:
    service = AdminDashboardService(repository)
    user = Principal(
        role=Role.USER,
        plan=Plan.PRO,
        user_id="user-1",
        username="student",
    )

    with pytest.raises(PermissionDeniedError):
        service.get_overview(user)
    with pytest.raises(PermissionDeniedError):
        service.list_users(user)
