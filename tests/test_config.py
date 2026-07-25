from course2career.config import Settings


def test_settings_repr_does_not_expose_secrets() -> None:
    settings = Settings(
        openai_api_key="openai-secret",
        deepseek_api_key="deepseek-secret",
        key_encryption_key="encryption-secret",
        bootstrap_admin_password="admin-secret",
    )

    rendered = repr(settings)

    assert "openai-secret" not in rendered
    assert "deepseek-secret" not in rendered
    assert "encryption-secret" not in rendered
    assert "admin-secret" not in rendered
