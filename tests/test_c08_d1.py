"""D1 production failure and recovery contracts, with synthetic credentials only."""

import logging
import os
from pathlib import Path

import certifi
import psycopg
import pytest
from psycopg.conninfo import conninfo_to_dict, make_conninfo
from streamlit.runtime.secrets import Secrets
from streamlit.testing.v1 import AppTest

from course2career.api_key_service import APIKeyService
from course2career.auth_service import AuthService
from course2career.config import load_settings
from course2career.data_migration import TABLES
from course2career.database_backend import (
    DatabaseBackend,
    DatabaseUnavailableError,
    classify_database_failure,
    log_database_startup_failure,
)
from course2career.database_migrations import schema_version
from course2career.key_encryption import (
    APIKeyCipher,
    EncryptedSecret,
    KeyDecryptionError,
)
from course2career.llm_provider import ProviderName
from course2career.postgres_repository import PostgresProductRepository


@pytest.mark.parametrize(
    "database_url",
    (
        "postgresql://127.0.0.1:1/test?sslmode=require",
        "postgresql://127.0.0.1:1/test?sslmode=disable",
        "postgresql://127.0.0.1:1/test?sslmode=verify-full",
    ),
)
def test_production_failure_never_creates_sqlite(
    monkeypatch, tmp_path: Path, database_url: str
) -> None:
    sqlite_path = tmp_path / "must-not-appear.db"
    monkeypatch.setenv("COURSE2CAREER_ENV", "production")
    monkeypatch.setenv("DATABASE_URL", database_url)
    monkeypatch.setenv("COURSE2CAREER_DATABASE_PATH", str(sqlite_path))
    app = AppTest.from_file(Path(__file__).resolve().parents[1] / "app.py").run(
        timeout=15
    )
    assert not app.exception
    assert any(
        item.value == "开发者模式暂时不可用：持久数据库连接或配置失败。"
        for item in app.error
    )
    assert not sqlite_path.exists()


def test_database_startup_log_never_contains_url_or_credentials(
    monkeypatch, caplog
) -> None:
    url = "postgresql://synthetic_user:synthetic_password@db.example.test/c2c?sslmode=verify-full"
    secret = "napi_synthetic_long_token_123456789"

    def failed_connect(*_args, **_kwargs):
        raise psycopg.OperationalError(
            f"certificate verify failed {url} password={secret} user=synthetic_user "
            f"DATABASE_URL={url} {secret}"
        )

    monkeypatch.setattr(psycopg, "connect", failed_connect)
    backend = DatabaseBackend(url=url, require_verified_tls=True)
    with pytest.raises(DatabaseUnavailableError) as error:
        backend.connect()
    with caplog.at_level(logging.ERROR):
        log_database_startup_failure(error.value)
    assert "failure_category=TLS_CERTIFICATE" in caplog.text
    for value in (url, "synthetic_user", "synthetic_password", secret, "DATABASE_URL="):
        assert value not in caplog.text


def test_production_connect_uses_explicit_certifi_bundle_over_url(monkeypatch) -> None:
    url = "postgresql://synthetic@db.example.test/c2c?sslmode=verify-full&sslrootcert=system"
    captured = {}

    def fake_connect(conninfo, **kwargs):
        captured.update(kwargs)
        assert conninfo == url
        return object()

    monkeypatch.setattr(psycopg, "connect", fake_connect)
    DatabaseBackend(url=url, require_verified_tls=True).connect()
    assert captured["sslmode"] == "verify-full"
    assert captured["sslrootcert"] == certifi.where()
    assert Path(captured["sslrootcert"]).is_file()
    effective = conninfo_to_dict(
        make_conninfo(
            url, sslmode=captured["sslmode"], sslrootcert=captured["sslrootcert"]
        )
    )
    assert effective["sslmode"] == "verify-full"
    assert effective["sslrootcert"] == certifi.where()


def test_local_postgres_test_does_not_override_ca_bundle(monkeypatch) -> None:
    captured = {}

    def fake_connect(_conninfo, **kwargs):
        captured.update(kwargs)
        return object()

    monkeypatch.setattr(psycopg, "connect", fake_connect)
    DatabaseBackend(
        url="postgresql://localhost/test?sslmode=disable",
        allow_insecure_local_test=True,
    ).connect()
    assert captured["sslmode"] == "disable"
    assert "sslrootcert" not in captured


@pytest.mark.parametrize(
    ("message", "expected"),
    (
        ("certificate verify failed", "TLS_CERTIFICATE"),
        ("server certificate hostname mismatch", "TLS_HOSTNAME"),
        ("password authentication failed for user secret-user", "AUTHENTICATION"),
        ("could not translate host name", "DNS"),
    ),
)
def test_database_startup_failure_categories(message: str, expected: str) -> None:
    assert classify_database_failure(psycopg.OperationalError(message)) == expected


def test_unknown_database_error_does_not_log_raw_secret(caplog) -> None:
    secret = "synthetic_credential_123456789012345"
    with caplog.at_level(logging.ERROR):
        log_database_startup_failure(Exception(f"unknown failure {secret}"))
        log_database_startup_failure(
            DatabaseUnavailableError(
                "safe", failure_category=secret, source_type=secret
            )
        )
    assert "database_startup_failure" in caplog.text
    assert "exception_type=Exception" in caplog.text
    assert "failure_category=UNKNOWN" in caplog.text
    assert secret not in caplog.text


def test_correct_master_key_decrypts_wrong_key_fails_safely() -> None:
    correct = APIKeyCipher(bytes(range(32)))
    wrong = APIKeyCipher(bytes(reversed(range(32))))
    secret = correct.encrypt(
        "synthetic-test-key", user_id="synthetic-user", provider=ProviderName.DEEPSEEK
    )
    stored = EncryptedSecret(secret.ciphertext, secret.nonce)
    assert (
        correct.decrypt(
            stored, user_id="synthetic-user", provider=ProviderName.DEEPSEEK
        )
        == "synthetic-test-key"
    )
    with pytest.raises(KeyDecryptionError, match="无法解密") as error:
        wrong.decrypt(stored, user_id="synthetic-user", provider=ProviderName.DEEPSEEK)
    assert "synthetic-test-key" not in str(error.value)


def test_root_streamlit_secrets_and_os_environment_share_config(
    monkeypatch, tmp_path: Path
) -> None:
    for name in (
        "COURSE2CAREER_ENV",
        "DATABASE_URL",
        "COURSE2CAREER_KEY_ENCRYPTION_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    secret_file = tmp_path / "secrets.toml"
    secret_file.write_text(
        'COURSE2CAREER_ENV = "production"\n'
        'DATABASE_URL = "postgresql://synthetic@localhost/test?sslmode=verify-full"\n'
        'COURSE2CAREER_KEY_ENCRYPTION_KEY = "synthetic-config-only"\n',
        encoding="utf-8",
    )
    from streamlit import config

    old_files = config.get_option("secrets.files")
    config.set_option("secrets.files", [str(secret_file)])
    secrets = Secrets()
    try:
        assert secrets.load_if_toml_exists()
        settings = load_settings()
        assert settings.production_mode
        assert settings.database_url == os.environ["DATABASE_URL"]
        assert (
            settings.key_encryption_key
            == os.environ["COURSE2CAREER_KEY_ENCRYPTION_KEY"]
        )
    finally:
        secrets._reset()
        config.set_option("secrets.files", old_files)


@pytest.mark.postgres_restore
def test_pg_dump_restore_keeps_assets_and_encryption_boundary() -> None:
    source_url = os.getenv("C08_TEST_DATABASE_URL")
    restore_url = os.getenv("C08_TEST_RESTORE_DATABASE_URL")
    if not source_url or not restore_url:
        pytest.skip("需要两份独立的合成 PostgreSQL 测试库")
    source = PostgresProductRepository(source_url, allow_insecure_local_test=True)
    restored = PostgresProductRepository(restore_url, allow_insecure_local_test=True)
    assert schema_version(source.backend) == schema_version(restored.backend) == 3
    with source._connect() as left, restored._connect() as right:
        source_counts = {
            table: left.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (*TABLES, "schema_migrations")
        }
        restored_counts = {
            table: right.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            for table in (*TABLES, "schema_migrations")
        }
    assert source_counts == restored_counts
    assert all(
        restored_counts[table] == 1
        for table in (
            "users",
            "user_byok_settings",
            "user_api_keys",
            "user_provider_profiles",
            "analysis_records",
            "api_usage",
        )
    )
    principal = AuthService(restored).authenticate(
        "fixture-user", "synthetic-password-789"
    )
    assert principal.byok_enabled
    correct_cipher = APIKeyCipher(bytes(range(32)))
    keys = APIKeyService(restored, correct_cipher)
    assert keys.get_key(principal, ProviderName.DEEPSEEK) == ("synthetic-deepseek-key")
    before = restored.get_api_key(principal.user_id, "deepseek")
    wrong_cipher = APIKeyCipher(bytes(reversed(range(32))))
    with pytest.raises(KeyDecryptionError, match="无法解密"):
        APIKeyService(restored, wrong_cipher).get_key(principal, ProviderName.DEEPSEEK)
    assert restored.get_api_key(principal.user_id, "deepseek") == before
    assert restored.list_analyses(principal.user_id)
