from datetime import UTC, datetime
from pathlib import Path

import pytest

from course2career.access_services import (
    AIUsageService,
    AnalysisRecordService,
    QuotaExceededError,
    SystemStatusService,
)
from course2career.llm_provider import LLMUsage
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


def _add_user(repository: SQLiteProductRepository, user_id: str, role: Role) -> None:
    repository.add(
        StoredUser(
            id=user_id,
            username=user_id,
            username_normalized=user_id,
            password_hash="not-used-in-this-test",
            role=role,
            plan=Plan.DEVELOPER if role == Role.DEVELOPER else Plan.FREE,
            created_time="2026-07-23T00:00:00+00:00",
        )
    )


def test_guest_system_ai_is_limited_to_two_calls_per_day(
    repository: SQLiteProductRepository,
) -> None:
    service = AIUsageService(repository)
    guest = Principal(role=Role.GUEST)

    service.start_call(guest, "system", "test-model", guest_session_id="guest-1")
    service.start_call(guest, "system", "test-model", guest_session_id="guest-1")

    with pytest.raises(QuotaExceededError, match="今日 AI 体验次数已用完"):
        service.start_call(guest, "system", "test-model", guest_session_id="guest-1")


def test_quota_status_reports_used_and_remaining_calls(
    repository: SQLiteProductRepository,
) -> None:
    service = AIUsageService(repository)
    guest = Principal(role=Role.GUEST)
    service.start_call(guest, "system", "test-model", guest_session_id="guest-1")

    status = service.get_quota_status(
        guest,
        "system",
        guest_session_id="guest-1",
    )

    assert status.used == 1
    assert status.limit == 2
    assert status.remaining == 1


def test_complete_call_persists_real_token_usage_and_configured_cost(
    repository: SQLiteProductRepository,
) -> None:
    service = AIUsageService(repository)
    guest = Principal(role=Role.GUEST)
    usage_id = service.start_call(
        guest,
        "system",
        "test-model",
        guest_session_id="guest-1",
        provider="deepseek",
    )

    service.complete_call(
        usage_id,
        success=True,
        usage=LLMUsage(input_tokens=200, output_tokens=100),
        input_cost_per_million=1.0,
        output_cost_per_million=2.0,
    )

    overview = repository.admin_overview(datetime.now(UTC))
    assert overview.total_tokens == 300
    assert overview.estimated_cost == pytest.approx(0.0004)


def test_developer_own_key_is_unlimited_but_user_is_denied(
    repository: SQLiteProductRepository,
) -> None:
    service = AIUsageService(repository)
    _add_user(repository, "dev-1", Role.DEVELOPER)
    _add_user(repository, "user-1", Role.USER)
    developer = Principal(
        role=Role.DEVELOPER,
        plan=Plan.DEVELOPER,
        user_id="dev-1",
        username="dev",
    )
    user = Principal(role=Role.USER, user_id="user-1", username="user")

    for _ in range(8):
        service.start_call(developer, "user", "test-model")

    with pytest.raises(PermissionDeniedError):
        service.start_call(user, "user", "test-model")


def test_analysis_history_is_saved_only_for_authenticated_owner(
    repository: SQLiteProductRepository,
) -> None:
    service = AnalysisRecordService(repository)
    _add_user(repository, "user-1", Role.USER)
    _add_user(repository, "user-2", Role.USER)
    owner = Principal(role=Role.USER, user_id="user-1", username="owner")
    other = Principal(role=Role.USER, user_id="user-2", username="other")
    report = AnalysisReport(
        job_title="数据分析师",
        overall_score=75,
        limitations=["仅用于学习规划。"],
    )

    record_id = service.save(owner, report)

    assert len(service.list_own(owner)) == 1
    assert service.list_own(other) == []
    restored = service.get_own(owner, record_id)
    assert restored is not None
    assert restored.report == report
    assert service.get_own(other, record_id) is None
    with pytest.raises(PermissionDeniedError):
        service.save(Principal(), report)


def test_system_status_is_admin_only(repository: SQLiteProductRepository) -> None:
    service = SystemStatusService(repository)
    admin = Principal(
        role=Role.ADMIN,
        plan=Plan.ADMIN,
        user_id="admin-1",
        username="admin",
    )

    status = service.get_status(admin)

    assert status.database_status == "正常"
    assert status.user_count == 0
    with pytest.raises(PermissionDeniedError):
        service.get_status(Principal(role=Role.USER, user_id="user-1", username="user"))
