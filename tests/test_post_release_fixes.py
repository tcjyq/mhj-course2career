"""Small regressions for the post-release production audit."""

import csv
import io
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

import httpx
import pytest
from openai import OpenAI

from course2career.access_services import AIUsageService
from course2career.api_key_service import APIKeyService
from course2career.auth_service import (
    AuthService,
    InvalidCredentialsError,
    InvalidSessionError,
    TooManyLoginAttemptsError,
)
from course2career.key_encryption import APIKeyCipher
from course2career.llm_provider import ProviderName
from course2career.llm_providers import DeepSeekProvider, ProviderError
from course2career.models import SkillMatch
from course2career.permissions import Principal, Role
from course2career.postgres_repository import PostgresProductRepository
from course2career.product_repository import SQLiteProductRepository
from course2career.provider_profile import ProviderProfileService
from course2career.report_exporter import export_skill_matches_csv
from course2career.ui.identity_state import clear_identity_state


def test_live_session_checks_revoke_expiry_and_identity(tmp_path):
    repo = SQLiteProductRepository(tmp_path / "sessions.db")
    auth = AuthService(repo)
    alice = auth.register("alice", "synthetic-password-123")
    bob = auth.register("bob", "synthetic-password-456")
    token = auth.create_session(alice)
    assert auth.refresh_session(alice, token) == alice
    assert auth.restore_session(token) == alice  # New tab / reload.
    with pytest.raises(InvalidSessionError):
        auth.refresh_session(bob, token)
    auth.revoke_session(token)
    with pytest.raises(InvalidSessionError):
        auth.refresh_session(alice, token)
    assert auth.restore_session(token) is None

    expired = auth.create_session(alice, now=datetime.now(UTC) - timedelta(days=8))
    with pytest.raises(InvalidSessionError):
        auth.refresh_session(alice, expired)
    current = auth.create_session(alice)
    repo.update_password_hash(alice.user_id, "synthetic-rotated-hash")
    with pytest.raises(InvalidSessionError):
        auth.refresh_session(alice, current)


def test_account_login_limit_survives_new_websocket_scope(tmp_path):
    repo = SQLiteProductRepository(tmp_path / "rate.db")
    auth = AuthService(repo)
    auth.register("alice", "synthetic-password-123")
    start = datetime(2026, 9, 29, tzinfo=UTC)
    for index in range(auth.MAX_ACCOUNT_FAILED_LOGINS):
        with pytest.raises(InvalidCredentialsError):
            auth.authenticate(
                "alice", "wrong-password", attempt_scope=f"tab-{index}", now=start
            )
    with pytest.raises(TooManyLoginAttemptsError):
        auth.authenticate(
            "alice", "synthetic-password-123", attempt_scope="new-tab", now=start
        )
    assert auth.authenticate(
        "alice",
        "synthetic-password-123",
        attempt_scope="new-tab",
        now=start + auth.LOGIN_WINDOW + timedelta(seconds=1),
    ).user_id
    assert repo.count_recent_failed_logins_for_username("alice", start) == 0


def test_logout_clears_analysis_only_and_requests_home():
    state = {
        "principal": Principal(),
        "auth_storage_nonce": "synthetic-nonce",
        "installation_id": "synthetic-installation",
        "job_analysis": "private JD",
        "analysis_report": "private report",
        "skill_editor": "private skill",
        "c2c_project_name_0": "private project",
        "c2c_internship_company_0": "private company",
        "c2c_minimum_degree": "private degree",
    }
    clear_identity_state(state)
    assert not any("private" in str(value) for value in state.values())
    assert state["identity_just_cleared"] is True
    assert state["analysis_form_epoch"] == 1
    assert state["auth_storage_nonce"] == "synthetic-nonce"
    assert state["installation_id"] == "synthetic-installation"


def test_csv_dangerous_text_is_neutralized_and_bom_kept():
    from course2career.models import AnalysisReport, SkillImportance, SkillMatchStatus

    matches = [
        SkillMatch(
            skill_name=name,
            importance=SkillImportance.CORE,
            support_score=80,
            status=SkillMatchStatus.STRONG,
        )
        for name in ("=1+1", "+1+1", "-1+1", "@SUM(1)", "中文技能", '"引用",\n换行')
    ]
    raw = export_skill_matches_csv(AnalysisReport(overall_score=80, matches=matches))
    assert raw.startswith(b"\xef\xbb\xbf")
    rows = list(csv.reader(io.StringIO(raw.decode("utf-8-sig"))))
    assert [row[0] for row in rows[1:5]] == ["'=1+1", "'+1+1", "'-1+1", "'@SUM(1)"]
    assert rows[5][0] == "中文技能"
    assert rows[6][0] == '"引用",\n换行'
    assert all(row[2] == "80.0" for row in rows[1:])


def _assert_atomic_byok(repo, monkeypatch):
    auth = AuthService(repo)
    user = auth.register("atomic_user", "synthetic-password-123")
    from course2career.byok_mode import BYOKModeService

    BYOKModeService(repo).set_enabled(user, True)
    user = auth.refresh_principal(user)
    keys = APIKeyService(repo, APIKeyCipher(bytes(range(32))))
    profiles = ProviderProfileService(repo)
    old_key = keys.prepare_key(user, ProviderName.OPENAI, "synthetic-old-key")
    old_profile = profiles.prepare_profile(
        user, ProviderName.OPENAI, "global", "old-model"
    )
    repo.save_provider_configuration(old_key, old_profile)
    new_key = keys.prepare_key(user, ProviderName.OPENAI, "synthetic-new-key")
    new_profile = profiles.prepare_profile(
        user, ProviderName.OPENAI, "global", "new-model"
    )

    def fail_profile(_connection, _profile):
        raise RuntimeError("synthetic profile failure")

    with monkeypatch.context() as patch:
        patch.setattr(repo, "_write_provider_profile", fail_profile)
        with pytest.raises(RuntimeError, match="synthetic profile failure"):
            repo.save_provider_configuration(new_key, new_profile)
    assert keys.get_key(user, ProviderName.OPENAI) == "synthetic-old-key"
    assert profiles.get(user, ProviderName.OPENAI).model_id == "old-model"


def test_sqlite_byok_configuration_is_atomic(tmp_path: Path, monkeypatch):
    _assert_atomic_byok(SQLiteProductRepository(tmp_path / "byok.db"), monkeypatch)


def test_env_template_starts_without_admin_bootstrap_and_uses_verified_model():
    import json

    root = Path(__file__).resolve().parents[1]
    settings = dict(
        line.split("=", 1)
        for line in (root / ".env.example").read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#") and "=" in line
    )
    assert settings["ADMIN_USERNAME"] == ""
    assert settings["ADMIN_PASSWORD"] == ""
    assert settings["ADMIN_PASSWORD_HASH"] == ""
    assert settings["DEEPSEEK_MODEL"] == "deepseek-flash"
    verified = json.loads(
        (root / "src/course2career/verified_models.json").read_text(encoding="utf-8")
    )
    assert "deepseek-flash" in str(verified)


@pytest.mark.parametrize("status", [500, 429, "timeout"])
def test_system_generation_does_not_retry_transport_errors(status):
    attempts = []

    def respond(request):
        attempts.append(request.url.path)
        if status == "timeout":
            raise httpx.ReadTimeout("synthetic timeout")
        return httpx.Response(status, json={"error": {"message": "synthetic failure"}})

    sdk = OpenAI(
        api_key="synthetic-key-never-sent",
        base_url="https://example.invalid/v1",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    )
    provider = DeepSeekProvider(
        api_key="synthetic-key-never-sent",
        model="deepseek-flash",
        sdk_client=sdk,
    )
    with pytest.raises(ProviderError):
        provider.extract_job_skills("synthetic JD")
    assert attempts == ["/v1/chat/completions"]


def test_failed_system_generation_keeps_one_reservation_for_one_attempt(tmp_path):
    repo = SQLiteProductRepository(tmp_path / "retry.db")
    usage = AIUsageService(repo)
    guest = Principal(role=Role.GUEST)
    usage_id = usage.start_call(
        guest,
        "system",
        "deepseek-flash",
        guest_session_id="synthetic-guest",
        provider="deepseek",
        installation_id="A" * 43,
    )
    attempts = []

    def fail(request):
        attempts.append(request.url.path)
        return httpx.Response(500, json={"error": {"message": "synthetic failure"}})

    provider = DeepSeekProvider(
        api_key="synthetic-key-never-sent",
        model="deepseek-flash",
        sdk_client=OpenAI(
            api_key="synthetic-key-never-sent",
            base_url="https://example.invalid/v1",
            max_retries=0,
            http_client=httpx.Client(transport=httpx.MockTransport(fail)),
        ),
    )
    with pytest.raises(ProviderError):
        provider.extract_job_skills("synthetic JD")
    usage.complete_call(usage_id, success=False)
    with repo._connect() as connection:
        rows = connection.execute(
            "SELECT id, status, quota_class FROM api_usage"
        ).fetchall()
    assert [(row[0], row[1], row[2]) for row in rows] == [
        (usage_id, "failed", "public_free")
    ]
    assert attempts == ["/v1/chat/completions"]


def test_system_404_fallback_is_exactly_one_explicit_extra_attempt():
    attempts = []

    def respond(request):
        attempts.append(request.url.path)
        if len(attempts) == 1:
            return httpx.Response(404, json={"error": {"message": "model missing"}})
        return httpx.Response(
            200,
            json={
                "id": "synthetic-completion",
                "object": "chat.completion",
                "created": 1,
                "model": "deepseek-v4-pro",
                "choices": [
                    {
                        "index": 0,
                        "finish_reason": "stop",
                        "message": {
                            "role": "assistant",
                            "content": '{"job_title":"synthetic","skills":[]}',
                        },
                    }
                ],
            },
        )

    sdk = OpenAI(
        api_key="synthetic-key-never-sent",
        base_url="https://example.invalid/v1",
        max_retries=0,
        http_client=httpx.Client(transport=httpx.MockTransport(respond)),
    )
    provider = DeepSeekProvider(
        api_key="synthetic-key-never-sent",
        model="deepseek-flash",
        fallback_models=("deepseek-v4-pro",),
        sdk_client=sdk,
    )
    assert provider.extract_job_skills("synthetic JD").job_title == "synthetic"
    assert attempts == ["/v1/chat/completions", "/v1/chat/completions"]


@pytest.mark.postgres
def test_postgres_session_rate_limit_and_byok_atomicity(monkeypatch):
    url = os.getenv("C08_TEST_DATABASE_URL")
    if not url or urlsplit(url).hostname not in {"localhost", "127.0.0.1", "::1"}:
        pytest.skip("仅在本机合成 PostgreSQL 测试库运行")
    repo = PostgresProductRepository(url, allow_insecure_local_test=True)
    with repo._connect() as connection:
        connection.execute(
            "TRUNCATE TABLE users, login_attempts, api_usage, analysis_records, "
            "user_api_keys, user_provider_profiles, user_byok_settings "
            "RESTART IDENTITY CASCADE"
        )
    _assert_atomic_byok(repo, monkeypatch)
    auth = AuthService(repo)
    user = auth.authenticate("atomic_user", "synthetic-password-123")
    token = auth.create_session(user)
    assert auth.refresh_session(user, token) == user
    auth.revoke_session(token)
    with pytest.raises(InvalidSessionError):
        auth.refresh_session(user, token)
    start = datetime(2026, 9, 29, tzinfo=UTC)
    for index in range(auth.MAX_ACCOUNT_FAILED_LOGINS):
        with pytest.raises(InvalidCredentialsError):
            auth.authenticate(
                "atomic_user",
                "wrong-password",
                attempt_scope=f"pg-tab-{index}",
                now=start,
            )
    with pytest.raises(TooManyLoginAttemptsError):
        auth.authenticate(
            "atomic_user",
            "synthetic-password-123",
            attempt_scope="pg-new-tab",
            now=start,
        )
