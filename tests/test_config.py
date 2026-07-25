from course2career.config import Settings, load_settings


def test_settings_repr_does_not_expose_secrets() -> None:
    settings = Settings(
        openai_api_key="openai-secret",
        deepseek_api_key="deepseek-secret",
        key_encryption_key="encryption-secret",
        admin_password="admin-secret",
        admin_password_hash="admin-hash-secret",
    )

    rendered = repr(settings)

    assert "openai-secret" not in rendered
    assert "deepseek-secret" not in rendered
    assert "encryption-secret" not in rendered
    assert "admin-secret" not in rendered
    assert "admin-hash-secret" not in rendered


def test_load_settings_reads_admin_credentials_from_environment(
    monkeypatch,
) -> None:
    monkeypatch.setenv("ADMIN_USERNAME", "owner_admin")
    monkeypatch.setenv("ADMIN_PASSWORD", "temporary-admin-password")
    monkeypatch.setenv("ADMIN_PASSWORD_HASH", "scrypt$hash-from-secret")

    settings = load_settings()

    assert settings.admin_username == "owner_admin"
    assert settings.admin_password == "temporary-admin-password"
    assert settings.admin_password_hash == "scrypt$hash-from-secret"
