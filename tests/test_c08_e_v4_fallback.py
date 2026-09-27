"""Synthetic, isolated verification of the emergency schema compatibility build."""

import hashlib
import os
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

import psycopg
import pytest
from psycopg import sql
from streamlit.testing.v1 import AppTest

from course2career.access_services import (
    AdminDashboardService,
    AIUsageService,
    AnalysisRecordService,
)
from course2career.api_key_service import APIKeyService
from course2career.auth_service import AuthService, RegistrationError
from course2career.byok_mode import BYOKModeService
from course2career.database_migrations import schema_version
from course2career.emergency_fallback import REGISTRATION_MESSAGE, SYSTEM_AI_MESSAGE
from course2career.jd_analyzer import analyze_job_description
from course2career.key_encryption import APIKeyCipher
from course2career.llm_provider import ProviderName
from course2career.models import AnalysisReport
from course2career.permissions import PermissionDeniedError, Principal
from course2career.postgres_repository import PostgresProductRepository
from course2career.product_repository import SQLiteProductRepository
from course2career.provider_profile import ProviderProfileService
from tests._fallback_support import seed_user

# Exact additive v4 DDL from C08-E1. Kept in the fixture so this fallback
# branch can be tested independently of the feature branch checkout.
E1_V4_DDL = (
    "ALTER TABLE users ADD COLUMN registration_installation_hash TEXT",
    "ALTER TABLE api_usage ADD COLUMN installation_hash TEXT",
    "ALTER TABLE api_usage ADD COLUMN quota_class TEXT",
    "CREATE INDEX idx_users_registration_installation_time "
    "ON users(registration_installation_hash, created_time)",
    "CREATE INDEX idx_api_usage_installation_class_time "
    "ON api_usage(installation_hash, quota_class, created_time)",
    "CREATE INDEX idx_api_usage_system_day ON api_usage(key_mode, created_time)",
    "INSERT INTO schema_migrations(version) VALUES (4)",
)
DATA_TABLES = (
    "users",
    "login_attempts",
    "api_usage",
    "analysis_records",
    "user_api_keys",
    "user_provider_profiles",
    "user_byok_settings",
    "auth_sessions",
    "schema_migrations",
)


@pytest.fixture
def isolated_postgres_url():
    base_url = os.getenv("C08_TEST_DATABASE_URL")
    if not base_url or urlsplit(base_url).hostname not in {
        "localhost",
        "127.0.0.1",
        "::1",
    }:
        pytest.skip("仅允许在本机合成 PostgreSQL 实例执行")
    database_name = f"c08_fallback_{uuid4().hex[:12]}"
    parts = urlsplit(base_url)
    maintenance_url = urlunsplit(parts._replace(path="/postgres"))
    with psycopg.connect(maintenance_url, autocommit=True) as connection:
        connection.execute(
            sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database_name))
        )
    try:
        yield urlunsplit(parts._replace(path=f"/{database_name}"))
    finally:
        with psycopg.connect(maintenance_url, autocommit=True) as connection:
            connection.execute(
                sql.SQL("DROP DATABASE {} WITH (FORCE)").format(
                    sql.Identifier(database_name)
                )
            )


def _snapshot(repository: PostgresProductRepository) -> str:
    digest = hashlib.sha256()
    with repository._connect() as connection:
        for table in DATA_TABLES:
            digest.update(table.encode())
            rows = connection.execute(
                f"SELECT row_to_json(t)::text AS record FROM {table} t"
            ).fetchall()
            for record in sorted(row["record"] for row in rows):
                digest.update(record.encode())
        for query in (
            "SELECT indexname || ':' || indexdef AS item "
            "FROM pg_indexes WHERE schemaname = 'public'",
            "SELECT table_name || '.' || column_name || ':' || data_type AS item "
            "FROM information_schema.columns WHERE table_schema = 'public'",
        ):
            rows = sorted(connection.execute(query).fetchall(), key=lambda r: r["item"])
            for row in rows:
                digest.update(row["item"].encode())
    return digest.hexdigest()


def test_sqlite_v4_is_read_only_compatible(tmp_path: Path) -> None:
    path = tmp_path / "fallback.db"
    SQLiteProductRepository(path)
    with sqlite3.connect(path) as connection:
        for statement in E1_V4_DDL:
            connection.execute(statement)
        before = "\n".join(connection.iterdump())
    reopened = SQLiteProductRepository(path)
    assert schema_version(reopened.backend) == 4
    with sqlite3.connect(path) as connection:
        assert "\n".join(connection.iterdump()) == before


def test_public_registration_and_system_ai_fail_closed(tmp_path: Path) -> None:
    repository = SQLiteProductRepository(tmp_path / "fallback.db")
    auth = AuthService(repository)
    with pytest.raises(RegistrationError, match=REGISTRATION_MESSAGE):
        auth.register_public("new_user", "synthetic-password-123")
    with pytest.raises(RegistrationError, match=REGISTRATION_MESSAGE):
        auth.register("new_user", "synthetic-password-123")
    assert repository.count_users() == 0
    with pytest.raises(PermissionDeniedError, match=SYSTEM_AI_MESSAGE):
        AIUsageService(repository).start_call(
            Principal(),
            "system",
            "synthetic-model",
            guest_session_id="synthetic-guest",
        )
    assert repository.admin_overview(datetime.now(UTC)).ai_call_count == 0


@pytest.mark.postgres
def test_postgres_v3_and_e1_v4_preserve_durable_assets(isolated_postgres_url) -> None:
    repository = PostgresProductRepository(
        isolated_postgres_url, allow_insecure_local_test=True
    )
    assert schema_version(repository.backend) == 3
    auth = AuthService(repository)
    owner = seed_user(repository, "fallback_owner", "synthetic-password-123")
    admin = auth.ensure_bootstrap_admin("fallback_admin", "synthetic-password-456")
    BYOKModeService(repository).set_enabled(owner, True)
    owner = auth.refresh_principal(owner)
    token = auth.create_session(owner)
    cipher = APIKeyCipher(bytes(range(32)))
    APIKeyService(repository, cipher).save_key(
        owner, ProviderName.DEEPSEEK, "synthetic-byok-key"
    )
    ProviderProfileService(repository).save(
        owner, ProviderName.DEEPSEEK, "global", "deepseek-flash"
    )
    report_id = AnalysisRecordService(repository).save(
        owner, AnalysisReport(overall_score=76)
    )
    legacy_usage_id = repository.reserve_ai_call(
        user_id=owner.user_id,
        guest_session_id=None,
        key_mode="user",
        model="deepseek-flash",
        provider="deepseek",
        daily_limit=None,
        created_time=datetime.now(UTC),
    )

    before_v3_startup = _snapshot(repository)
    v3_fallback = PostgresProductRepository(
        isolated_postgres_url, allow_insecure_local_test=True
    )
    assert schema_version(v3_fallback.backend) == 3
    assert _snapshot(v3_fallback) == before_v3_startup
    assert AuthService(v3_fallback).restore_session(token).user_id == owner.user_id

    with repository._connect() as connection:
        for statement in E1_V4_DDL:
            connection.execute(statement)
        installation_hash = hashlib.sha256(b"synthetic-installation").hexdigest()
        connection.execute(
            "UPDATE users SET registration_installation_hash = ? WHERE id = ?",
            (installation_hash, owner.user_id),
        )
        connection.execute(
            "UPDATE api_usage SET installation_hash = ?, quota_class = ? WHERE id = ?",
            (installation_hash, "assigned_20", legacy_usage_id),
        )
    assert schema_version(repository.backend) == 4
    before_v4_startup = _snapshot(repository)
    fallback = PostgresProductRepository(
        isolated_postgres_url, allow_insecure_local_test=True
    )
    assert schema_version(fallback.backend) == 4
    assert _snapshot(fallback) == before_v4_startup

    fallback_auth = AuthService(fallback)
    assert (
        fallback_auth.authenticate("fallback_owner", "synthetic-password-123").user_id
        == owner.user_id
    )
    restored = fallback_auth.restore_session(token)
    assert restored is not None and restored.user_id == owner.user_id
    assert restored.byok_enabled
    assert fallback.get_analysis(owner.user_id, report_id) is not None
    assert len(fallback.list_analyses(owner.user_id)) == 1
    assert (
        APIKeyService(fallback, cipher).get_key(restored, ProviderName.DEEPSEEK)
        == "synthetic-byok-key"
    )
    assert (
        ProviderProfileService(fallback).get(restored, ProviderName.DEEPSEEK).model_id
        == "deepseek-flash"
    )
    overview = AdminDashboardService(fallback).get_overview(admin)
    assert overview.user_count == 2
    assert overview.ai_call_count == 1
    assert len(AdminDashboardService(fallback).list_users(admin)) == 2
    assert (
        analyze_job_description(
            "数据分析实习生。核心要求：熟练掌握 Python 和 SQL，能够完成数据清洗与查询。"
        ).source
        == "rules"
    )
    with pytest.raises(RegistrationError, match=REGISTRATION_MESSAGE):
        fallback_auth.register_public("new_public", "synthetic-password-789")
    with pytest.raises(PermissionDeniedError, match=SYSTEM_AI_MESSAGE):
        AIUsageService(fallback).start_call(
            restored, "system", "deepseek-flash", provider="deepseek"
        )
    byok_usage = AIUsageService(fallback).start_call(
        restored, "user", "deepseek-flash", provider="deepseek"
    )
    AIUsageService(fallback).complete_call(byok_usage, success=False)
    fallback_auth.revoke_session(token)
    assert fallback_auth.restore_session(token) is None

    with fallback._connect() as connection:
        connection.execute("INSERT INTO schema_migrations(version) VALUES (5)")
    with pytest.raises(RuntimeError, match="高于"):
        PostgresProductRepository(isolated_postgres_url, allow_insecure_local_test=True)


def test_login_page_shows_emergency_message(tmp_path: Path) -> None:
    path = tmp_path / "ui.db"
    app = AppTest.from_string(
        f"""
from course2career.auth_service import AuthService
from course2career.permissions import Principal
from course2career.product_repository import SQLiteProductRepository
from course2career.ui.auth_page import render_auth_page
repository = SQLiteProductRepository(r"{path.as_posix()}")
render_auth_page(Principal(), AuthService(repository))
"""
    ).run()
    assert not app.exception
    assert {button.label for button in app.button} == {"登录"}
    assert any(REGISTRATION_MESSAGE in item.value for item in app.info)
