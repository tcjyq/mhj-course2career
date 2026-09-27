"""C08-E abuse controls use only synthetic browser markers and provider-free calls."""

import hashlib
import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit
from uuid import uuid4

import httpx
import pytest

from course2career.access_services import AIUsageService, QuotaExceededError
from course2career.auth_service import AuthService, RegistrationError
from course2career.config import Settings
from course2career.installation_identity import installation_hash
from course2career.permissions import Plan, Principal, Role
from course2career.postgres_repository import PostgresProductRepository
from course2career.product_repository import QuotaConflictError, SQLiteProductRepository
from course2career.turnstile import (
    TEST_SECRET_KEY,
    TEST_SITE_KEY,
    TurnstileError,
    TurnstileVerifier,
    build_registration_verifier,
)
from course2career.user_repository import StoredUser

MARKER_A = "A" * 43
MARKER_B = "B" * 43
HASH_A = installation_hash(MARKER_A)
HASH_B = installation_hash(MARKER_B)
NOW = datetime(2026, 9, 27, 12, tzinfo=UTC)


def _verifier(*, response=None, fail=False):
    result = response or {
        "success": True,
        "hostname": "localhost",
        "action": "register",
    }

    def handler(request):
        assert request.url.host == "challenges.cloudflare.com"
        if fail:
            raise httpx.ReadTimeout("synthetic timeout")
        return httpx.Response(200, json=result)

    return TurnstileVerifier(
        "synthetic-test-secret",
        ("localhost",),
        httpx.Client(transport=httpx.MockTransport(handler)),
    )


def _register(auth, name, marker=MARKER_A, now=NOW, verifier=None):
    return auth.register_public(
        name,
        "synthetic-password-123",
        installation_id=marker,
        turnstile_token="synthetic-challenge",
        verifier=verifier or _verifier(),
        now=now,
    )


def _user(repo, name, *, plan=Plan.FREE, role=Role.USER, source=None, created=NOW):
    user_id = str(uuid4())
    repo.add(
        StoredUser(
            id=user_id,
            username=name,
            username_normalized=name,
            password_hash="synthetic-hash",
            role=role,
            plan=plan,
            created_time=created.isoformat(),
        )
    )
    if source is not None:
        with repo._connect() as connection:
            connection.execute(
                "UPDATE users SET registration_installation_hash=? WHERE id=?",
                (source, user_id),
            )
    return user_id


def _reserve(
    repo,
    *,
    user_id=None,
    guest=None,
    marker=HASH_A,
    quota_class="public_free",
    user_limit=5,
    install_limit=10,
    public_limit=100,
    absolute_limit=120,
    now=NOW,
    key_mode="system",
):
    return repo.reserve_ai_call(
        user_id=user_id,
        guest_session_id=guest,
        key_mode=key_mode,
        model="synthetic-model",
        provider="deepseek",
        daily_limit=user_limit,
        created_time=now,
        installation_hash=marker,
        quota_class=quota_class,
        installation_limit=install_limit,
        public_global_limit=public_limit,
        absolute_limit=absolute_limit,
    )


def test_turnstile_siteverify_failure_modes_and_no_secret_log(caplog):
    _verifier().validate("synthetic-challenge")
    for response in (
        {"success": False, "hostname": "localhost", "action": "register"},
        {"success": True, "hostname": "attacker.example", "action": "register"},
        {"success": True, "hostname": "localhost", "action": "login"},
    ):
        with pytest.raises(TurnstileError):
            _verifier(response=response).validate("synthetic-challenge")
    with pytest.raises(TurnstileError):
        _verifier(fail=True).validate("synthetic-challenge")
    with pytest.raises(TurnstileError):
        _verifier().validate(None)
    attempts = set()

    def replay_handler(request):
        token = request.content.decode()
        result = {
            "success": token not in attempts,
            "hostname": "localhost",
            "action": "register",
        }
        attempts.add(token)
        return httpx.Response(200, json=result)

    verifier = TurnstileVerifier(
        "synthetic-test-secret",
        ("localhost",),
        httpx.Client(transport=httpx.MockTransport(replay_handler)),
    )
    verifier.validate("synthetic-challenge")
    with pytest.raises(TurnstileError):
        verifier.validate("synthetic-challenge")
    assert "synthetic-challenge" not in caplog.text
    assert "synthetic-test-secret" not in caplog.text
    assert "synthetic-test-secret" not in repr(verifier)


def test_official_dummy_keys_only_use_local_stub():
    local = Settings(
        turnstile_site_key=TEST_SITE_KEY,
        turnstile_secret_key=TEST_SECRET_KEY,
        turnstile_allowed_hostnames=("localhost",),
    )
    build_registration_verifier(local).validate("XXXX.DUMMY.TOKEN.XXXX")
    production = Settings(
        production_mode=True,
        turnstile_site_key=TEST_SITE_KEY,
        turnstile_secret_key=TEST_SECRET_KEY,
        turnstile_allowed_hostnames=("localhost",),
    )
    assert build_registration_verifier(production).client is None


def test_registration_windows_hash_and_fail_closed(tmp_path: Path, monkeypatch):
    repo = SQLiteProductRepository(tmp_path / "registration.db")
    auth = AuthService(repo)
    _register(auth, "alice")
    _register(auth, "bob")
    with pytest.raises(RegistrationError, match="近期"):
        _register(auth, "carol")
    with repo._connect() as connection:
        rows = connection.execute(
            "SELECT registration_installation_hash FROM users"
        ).fetchall()
    assert len(rows) == 2
    assert all(row[0] == hashlib.sha256(MARKER_A.encode()).hexdigest() for row in rows)
    db_bytes = (tmp_path / "registration.db").read_bytes()
    assert MARKER_A.encode() not in db_bytes
    assert b"synthetic-challenge" not in db_bytes

    def forbidden_password_hash(_password):
        raise AssertionError("Siteverify must precede password hashing")

    monkeypatch.setattr(
        "course2career.auth_service.hash_password", forbidden_password_hash
    )
    with pytest.raises(TurnstileError):
        _register(auth, "denied", MARKER_B, verifier=_verifier(fail=True))
    assert auth.repository.find_by_normalized_username("denied") is None
    with pytest.raises(RegistrationError):
        _register(auth, "noid", "invalid")


def test_sqlite_concurrent_registration_final_slot(tmp_path: Path):
    repo = SQLiteProductRepository(tmp_path / "registration-concurrent.db")
    auth = AuthService(repo)
    _register(auth, "first")

    def create(name):
        try:
            _register(auth, name)
            return True
        except RegistrationError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(create, ("second", "third"))) == 1
    assert repo.count_users() == 2


def test_registration_rolling_week_and_expired_hash_cleanup(tmp_path: Path):
    repo = SQLiteProductRepository(tmp_path / "windows.db")
    auth = AuthService(repo)
    _register(auth, "oldone", now=NOW - timedelta(days=3))
    _register(auth, "oldtwo", now=NOW - timedelta(days=3, hours=-1))
    _register(auth, "oldthree", now=NOW - timedelta(days=1, hours=20))
    with pytest.raises(RegistrationError, match="近期"):
        _register(auth, "fourth", now=NOW)
    _user(repo, "expired_source", source=HASH_B, created=NOW - timedelta(days=31))
    with pytest.raises(RegistrationError):
        _register(auth, "fifth", now=NOW)
    _register(auth, "otherdevice", marker=MARKER_B, now=NOW)
    with repo._connect() as connection:
        expired = connection.execute(
            "SELECT registration_installation_hash FROM users "
            "WHERE username='expired_source'"
        ).fetchone()[0]
    assert expired is None


def test_system_quota_source_current_global_absolute_and_day_boundary(tmp_path: Path):
    repo = SQLiteProductRepository(tmp_path / "quota.db")
    users = [_user(repo, f"free{i}", source=HASH_A) for i in range(3)]
    for user_id in users[:2]:
        for _ in range(5):
            _reserve(repo, user_id=user_id, marker=HASH_B)
    with pytest.raises(QuotaConflictError):
        _reserve(repo, user_id=users[2], marker=HASH_B)
    assert (
        repo.count_ai_calls_today(
            user_id=users[2], guest_session_id=None, key_mode="system", created_time=NOW
        )
        == 0
    )
    # A fresh day in Asia/Shanghai resets every daily bucket.
    _reserve(repo, user_id=users[2], marker=HASH_B, now=NOW + timedelta(days=1))
    pro = _user(repo, "pro", plan=Plan.PRO, source=HASH_A)
    for _ in range(20):
        _reserve(
            repo,
            user_id=pro,
            marker=HASH_B,
            quota_class="assigned_20",
            user_limit=20,
            install_limit=20,
            now=NOW + timedelta(days=2),
        )
    with pytest.raises(QuotaConflictError):
        _reserve(
            repo,
            guest="extra",
            marker=HASH_B,
            quota_class="assigned_20",
            user_limit=100,
            install_limit=20,
            now=NOW + timedelta(days=2),
        )
    # Public fuse includes non-admin calls across installations and classes.
    with pytest.raises(QuotaConflictError):
        _reserve(
            repo,
            guest="global",
            marker=HASH_A,
            user_limit=100,
            install_limit=100,
            public_limit=20,
            now=NOW + timedelta(days=2),
        )
    admin = _user(repo, "admin", plan=Plan.ADMIN, role=Role.ADMIN)
    with pytest.raises(QuotaConflictError):
        _reserve(
            repo,
            user_id=admin,
            marker=None,
            quota_class="admin",
            user_limit=None,
            install_limit=None,
            absolute_limit=20,
            now=NOW + timedelta(days=2),
        )


def test_exact_public_100_absolute_120_and_shanghai_midnight(tmp_path: Path):
    repo = SQLiteProductRepository(tmp_path / "fuses.db")
    for index in range(100):
        _reserve(repo, guest=f"guest-{index}", install_limit=200, user_limit=2)
    with pytest.raises(QuotaConflictError):
        _reserve(repo, guest="guest-101", install_limit=200, user_limit=2)
    admin = _user(repo, "fuse_admin", plan=Plan.ADMIN, role=Role.ADMIN)
    for _ in range(20):
        _reserve(
            repo,
            user_id=admin,
            marker=None,
            quota_class="admin",
            user_limit=None,
            install_limit=None,
        )
    with pytest.raises(QuotaConflictError):
        _reserve(
            repo,
            user_id=admin,
            marker=None,
            quota_class="admin",
            user_limit=None,
            install_limit=None,
        )
    before = datetime(2026, 9, 28, 15, 59, tzinfo=UTC)
    after = datetime(2026, 9, 28, 16, 1, tzinfo=UTC)
    _reserve(repo, guest="midnight", marker=HASH_B, user_limit=1, now=before)
    _reserve(repo, guest="midnight", marker=HASH_B, user_limit=1, now=after)


def test_service_guest_free_developer_and_byok_boundary(tmp_path: Path):
    repo = SQLiteProductRepository(tmp_path / "service.db")
    service = AIUsageService(repo, Settings())
    guest = Principal()
    for _ in range(2):
        service.start_call(
            guest,
            "system",
            "synthetic",
            guest_session_id="g1",
            installation_id=MARKER_A,
        )
    with pytest.raises(QuotaExceededError):
        service.start_call(
            guest,
            "system",
            "synthetic",
            guest_session_id="g1",
            installation_id=MARKER_A,
        )
    with pytest.raises(QuotaExceededError):
        service.start_call(guest, "system", "synthetic", guest_session_id="g2")
    free_id = _user(repo, "free")
    free = Principal(role=Role.USER, plan=Plan.FREE, user_id=free_id, byok_enabled=True)
    for _ in range(5):
        service.start_call(free, "system", "synthetic", installation_id=MARKER_B)
    with pytest.raises(QuotaExceededError):
        service.start_call(free, "system", "synthetic", installation_id=MARKER_B)
    dev_id = _user(repo, "developer_free", role=Role.DEVELOPER)
    developer_free = Principal(
        role=Role.DEVELOPER,
        plan=Plan.FREE,
        user_id=dev_id,
        byok_enabled=True,
    )
    for _ in range(5):
        service.start_call(
            developer_free, "system", "synthetic", installation_id=MARKER_A
        )
    with pytest.raises(QuotaExceededError):
        service.start_call(
            developer_free, "system", "synthetic", installation_id=MARKER_A
        )
    assert (
        repo.count_ai_calls_today(
            user_id=free_id,
            guest_session_id=None,
            key_mode="user",
            created_time=datetime.now(UTC),
        )
        == 0
    )


def test_legacy_null_source_and_usage_hash_cleanup(tmp_path: Path):
    repo = SQLiteProductRepository(tmp_path / "legacy.db")
    user_id = _user(repo, "legacy", created=NOW - timedelta(days=100))
    old_id = _reserve(repo, user_id=user_id, marker=HASH_A, now=NOW - timedelta(days=9))
    with pytest.raises(QuotaConflictError):
        _reserve(repo, user_id=user_id, marker=HASH_B, user_limit=0, now=NOW)
    _reserve(repo, user_id=user_id, marker=HASH_B, now=NOW)
    with repo._connect() as connection:
        row = connection.execute(
            "SELECT installation_hash FROM api_usage WHERE id=?", (old_id,)
        ).fetchone()
    assert row[0] is None


@pytest.mark.postgres
def test_postgres_concurrent_last_registration_and_quota_slot():
    url = os.getenv("C08_TEST_DATABASE_URL")
    if not url or urlsplit(url).hostname not in {"localhost", "127.0.0.1", "::1"}:
        pytest.skip("只允许独立的 CI 本机 PostgreSQL")
    repo = PostgresProductRepository(url, allow_insecure_local_test=True)
    suffix = uuid4().hex[:12]
    try:
        _assert_postgres_final_slots(repo, suffix)
    finally:
        # Remove only this test's synthetic rows before the CI backup drill.
        with repo._connect() as connection:
            connection.execute(
                "DELETE FROM users WHERE username_normalized LIKE ? "
                "OR username_normalized LIKE ?",
                (f"c08e_{suffix}_%", f"c08e_reg_{suffix}_%"),
            )


def _assert_postgres_final_slots(repo: PostgresProductRepository, suffix: str):
    # The repository accepts a hash; no plaintext marker enters the database.
    marker = hashlib.sha256(suffix.encode()).hexdigest()
    users = [_user(repo, f"c08e_{suffix}_{i}", source=marker) for i in range(2)]

    def reserve(user_id):
        try:
            _reserve(
                repo,
                user_id=user_id,
                marker=marker,
                install_limit=1,
                public_limit=100000,
                absolute_limit=100000,
            )
            return True
        except QuotaConflictError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(reserve, users)) == 1

    browser_id = suffix + "C" * 31
    auth = AuthService(repo)
    _register(auth, f"c08e_reg_{suffix}_first", browser_id)

    def register(name):
        try:
            _register(auth, name, browser_id)
            return True
        except RegistrationError:
            return False

    names = [f"c08e_reg_{suffix}_{i}" for i in range(2)]
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sum(pool.map(register, names)) == 1
