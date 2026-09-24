"""C08-D0 local migration and independent PostgreSQL integration checks."""

import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from streamlit.testing.v1 import AppTest

from course2career.access_services import AIUsageService
from course2career.api_key_service import APIKeyService
from course2career.auth_service import AuthService
from course2career.byok_mode import BYOKModeService
from course2career.data_migration import (
    TABLES,
    copy_sqlite_to_postgres,
    prepare_sqlite_copy,
)
from course2career.database_backend import DatabaseBackend, DatabaseConfigurationError
from course2career.database_migrations import schema_version
from course2career.key_encryption import APIKeyCipher
from course2career.llm_provider import LLMUsage, ProviderName
from course2career.models import AnalysisReport
from course2career.permissions import PermissionDeniedError
from course2career.postgres_repository import PostgresProductRepository
from course2career.product_repository import SQLiteProductRepository
from course2career.provider_profile import ProviderProfileService
from course2career.provider_verification import (
    DEFAULT_RECORD_PATH,
    get_record,
)


def test_sqlite_fresh_schema_version_and_reconnect(tmp_path):
    path = tmp_path / "local.db"
    first = SQLiteProductRepository(path)
    assert schema_version(first.backend) == 2
    assert SQLiteProductRepository(path).count_users() == 0
    with sqlite3.connect(path) as connection:
        names = {row[0] for row in connection.execute("SELECT name FROM sqlite_master")}
    assert set(TABLES) | {"schema_migrations"} <= names


def test_newer_sqlite_schema_refuses_downgrade(tmp_path):
    path = tmp_path / "newer.db"
    SQLiteProductRepository(path)
    with sqlite3.connect(path) as connection:
        connection.execute("INSERT INTO schema_migrations(version) VALUES (3)")
    with pytest.raises(RuntimeError, match="高于"):
        SQLiteProductRepository(path)


def test_old_sqlite_snapshot_upgrades_in_copy_only(tmp_path):
    old = tmp_path / "old-c07.db"
    copy = tmp_path / "upgraded.db"
    with sqlite3.connect(old) as connection:
        connection.execute(
            "CREATE TABLE users (id TEXT PRIMARY KEY, username TEXT NOT NULL, "
            "username_normalized TEXT NOT NULL UNIQUE, password_hash TEXT NOT NULL, "
            "role TEXT NOT NULL, plan TEXT NOT NULL DEFAULT 'free', "
            "created_time TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT INTO users VALUES (?, ?, ?, ?, ?, ?, ?)",
            ("legacy", "legacy", "legacy", "synthetic-hash", "developer", "free", "t"),
        )
    prepare_sqlite_copy(old, copy)
    assert SQLiteProductRepository(copy).find_by_id("legacy").plan.value == "developer"
    assert schema_version(DatabaseBackend(database_path=copy)) == 2
    with sqlite3.connect(old) as connection:
        assert connection.execute("PRAGMA table_info(users)").fetchall()[-1][1] == (
            "created_time"
        )
        assert (
            connection.execute(
                "SELECT name FROM sqlite_master WHERE name = 'schema_migrations'"
            ).fetchone()
            is None
        )


def test_production_database_rejects_local_or_unencrypted_targets(tmp_path):
    with pytest.raises(DatabaseConfigurationError):
        DatabaseBackend(url="sqlite:///temporary.db")
    with pytest.raises(DatabaseConfigurationError):
        DatabaseBackend(url="postgresql://localhost/example?sslmode=disable")
    with pytest.raises(DatabaseConfigurationError):
        DatabaseBackend(
            url="postgresql://localhost/example?sslmode=require&sslmode=disable"
        )
    with pytest.raises(DatabaseConfigurationError):
        DatabaseBackend(database_path=tmp_path / "x.db", url="postgresql://x/y")


def test_local_validation_file_does_not_certify_production():
    assert DEFAULT_RECORD_PATH != get_record.__defaults__[0]
    assert get_record(ProviderName.OPENAI, "global", "local-only") is None


def test_production_without_database_fails_closed(monkeypatch):
    monkeypatch.setenv("COURSE2CAREER_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", "")
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run()
    assert not app.exception
    assert any("开发者模式暂时不可用" in item.value for item in app.error)


@pytest.mark.postgres
def test_postgres_persists_all_user_assets_and_migrates_synthetic_sqlite(tmp_path):
    url = os.getenv("C08_TEST_DATABASE_URL")
    if not url:
        pytest.skip("需要独立的 C08_TEST_DATABASE_URL 测试实例")
    if urlsplit(url).hostname not in {"localhost", "127.0.0.1", "::1"}:
        pytest.skip("此清空测试仅允许 CI 本机 PostgreSQL")
    repo = PostgresProductRepository(url, allow_insecure_local_test=True)
    with repo._connect() as connection:
        connection.execute(
            "TRUNCATE TABLE users, login_attempts, api_usage, analysis_records, "
            "user_api_keys, user_provider_profiles, user_byok_settings "
            "RESTART IDENTITY CASCADE"
        )
    assert schema_version(repo.backend) == 2
    auth = AuthService(repo)
    alice = auth.register("alice", "synthetic-password-123")
    bob = auth.register("bob", "synthetic-password-456")
    assert auth.authenticate("alice", "synthetic-password-123").user_id == alice.user_id
    modes = BYOKModeService(repo)
    modes.set_enabled(alice, True)
    enabled = auth.refresh_principal(alice)
    cipher = APIKeyCipher(bytes(range(32)))
    keys = APIKeyService(repo, cipher)
    keys.save_key(enabled, ProviderName.OPENAI, "synthetic-key-123456")
    profiles = ProviderProfileService(repo)
    profiles.save(enabled, ProviderName.OPENAI, "global", "gpt-5.6-luna")
    report_id = repo.add_analysis(alice.user_id, AnalysisReport(overall_score=72))
    usage = AIUsageService(repo)
    call_id = usage.start_call(enabled, "user", "gpt-5.6-luna")
    usage.complete_call(
        call_id,
        success=True,
        usage=LLMUsage(input_tokens=30, output_tokens=12, model="gpt-5.6-luna"),
    )
    assert (
        repo.count_ai_calls_today(
            user_id=alice.user_id,
            guest_session_id=None,
            key_mode="user",
            created_time=datetime.now(UTC),
        )
        == 1
    )
    modes.set_enabled(enabled, False)
    with pytest.raises(PermissionDeniedError):
        keys.get_key(enabled, ProviderName.OPENAI)
    reopened = PostgresProductRepository(url, allow_insecure_local_test=True)
    assert reopened.find_by_id(alice.user_id) is not None
    assert reopened.get_analysis(alice.user_id, report_id) is not None
    assert reopened.get_analysis(bob.user_id, report_id) is None
    assert reopened.get_api_key(bob.user_id, "openai") is None
    assert (
        reopened.get_provider_profile(alice.user_id, "openai").model_id
        == "gpt-5.6-luna"
    )
    assert reopened.get_byok_mode(alice.user_id).byok_enabled is False
    assert (
        reopened.count_ai_calls_today(
            user_id=alice.user_id,
            guest_session_id=None,
            key_mode="user",
            created_time=datetime.now(UTC),
        )
        == 1
    )
    BYOKModeService(reopened).set_enabled(alice, True)
    restored = AuthService(reopened).refresh_principal(alice)
    assert APIKeyService(reopened, cipher).get_key(restored, ProviderName.OPENAI) == (
        "synthetic-key-123456"
    )

    with reopened._connect() as connection:
        connection.execute(
            "TRUNCATE TABLE users, login_attempts, api_usage, analysis_records, "
            "user_api_keys, user_provider_profiles, user_byok_settings "
            "RESTART IDENTITY CASCADE"
        )
    source = SQLiteProductRepository(tmp_path / "synthetic.db")
    synthetic = AuthService(source).register("fixture-user", "synthetic-password-789")
    BYOKModeService(source).set_enabled(synthetic, True)
    APIKeyService(source, cipher).save_key(
        AuthService(source).refresh_principal(synthetic),
        ProviderName.DEEPSEEK,
        "synthetic-deepseek-key",
    )
    fixture_enabled = AuthService(source).refresh_principal(synthetic)
    ProviderProfileService(source).save(
        fixture_enabled, ProviderName.DEEPSEEK, "global", "deepseek-flash"
    )
    source.add_analysis(synthetic.user_id, AnalysisReport(overall_score=81))
    fixture_call = AIUsageService(source).start_call(
        fixture_enabled, "user", "deepseek-flash", provider="deepseek"
    )
    AIUsageService(source).complete_call(
        fixture_call,
        success=True,
        usage=LLMUsage(input_tokens=8, output_tokens=4, model="deepseek-flash"),
    )
    counts = copy_sqlite_to_postgres(
        source.database_path, url, allow_insecure_local_test=True
    )
    assert counts["users"] == counts["user_api_keys"] == 1
    assert counts["user_provider_profiles"] == counts["analysis_records"] == 1
    assert counts["api_usage"] == 1
    migrated = PostgresProductRepository(url, allow_insecure_local_test=True)
    assert migrated.find_by_id(synthetic.user_id) is not None
    assert (
        APIKeyService(migrated, cipher).get_key(
            AuthService(migrated).refresh_principal(synthetic), ProviderName.DEEPSEEK
        )
        == "synthetic-deepseek-key"
    )
    with pytest.raises(RuntimeError, match="不为空"):
        copy_sqlite_to_postgres(
            source.database_path, url, allow_insecure_local_test=True
        )
