from course2career.config import Settings, load_settings


def test_deepseek_model_management_defaults_to_auto_safe(monkeypatch) -> None:
    monkeypatch.delenv("DEEPSEEK_MODEL_MODE", raising=False)

    settings = load_settings()

    assert settings.deepseek_model_mode == "auto_safe"


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


def test_load_settings_reads_nonnegative_model_costs(monkeypatch) -> None:
    monkeypatch.setenv("DEEPSEEK_INPUT_COST_PER_MILLION", "2.5")
    monkeypatch.setenv("DEEPSEEK_OUTPUT_COST_PER_MILLION", "10")
    monkeypatch.setenv("OPENAI_INPUT_COST_PER_MILLION", "-1")
    monkeypatch.setenv("OPENAI_OUTPUT_COST_PER_MILLION", "invalid")

    settings = load_settings()

    assert settings.deepseek_input_cost_per_million == 2.5
    assert settings.deepseek_output_cost_per_million == 10
    assert settings.openai_input_cost_per_million == 0
    assert settings.openai_output_cost_per_million == 0


def test_load_settings_reads_safe_deepseek_model_management_options(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_MODEL_MODE", "auto_safe")
    monkeypatch.setenv(
        "DEEPSEEK_MODEL_PREFERENCE",
        "deepseek-v4-pro, deepseek-v4-flash, deepseek-v4-pro",
    )
    monkeypatch.setenv("DEEPSEEK_MODEL_CACHE_SECONDS", "900")
    monkeypatch.setenv("DEEPSEEK_MODEL_STALE_SECONDS", "7200")
    monkeypatch.setenv("DEEPSEEK_MAX_OUTPUT_TOKENS", "1200")
    monkeypatch.setenv("SYSTEM_AI_ENABLED", "false")

    settings = load_settings()

    assert settings.deepseek_model_mode == "auto_safe"
    assert settings.deepseek_model_preference == (
        "deepseek-v4-pro",
        "deepseek-v4-flash",
    )
    assert settings.deepseek_model_cache_seconds == 900
    assert settings.deepseek_model_stale_seconds == 7200
    assert settings.deepseek_max_output_tokens == 1200
    assert settings.system_ai_enabled is False


def test_load_settings_falls_back_from_invalid_model_management_options(
    monkeypatch,
) -> None:
    monkeypatch.setenv("DEEPSEEK_MODEL_MODE", "latest")
    monkeypatch.setenv("DEEPSEEK_MODEL_PREFERENCE", "")
    monkeypatch.setenv("DEEPSEEK_MODEL_CACHE_SECONDS", "invalid")
    monkeypatch.setenv("DEEPSEEK_MODEL_STALE_SECONDS", "-1")
    monkeypatch.setenv("DEEPSEEK_MAX_OUTPUT_TOKENS", "0")

    settings = load_settings()

    assert settings.deepseek_model_mode == "pinned"
    assert settings.deepseek_model_preference == (
        "deepseek-v4-flash",
        "deepseek-v4-pro",
    )
    assert settings.deepseek_model_cache_seconds == 1800
    assert settings.deepseek_model_stale_seconds == 86400
    assert settings.deepseek_max_output_tokens == 1500
