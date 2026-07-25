import base64
import sqlite3
from pathlib import Path

import pytest

from course2career.api_key_service import APIKeyService
from course2career.key_encryption import (
    APIKeyCipher,
    KeyDecryptionError,
    KeyEncryptionConfigurationError,
)
from course2career.llm_provider import ProviderName
from course2career.permissions import (
    PermissionDeniedError,
    Plan,
    Principal,
    Role,
)
from course2career.product_repository import SQLiteProductRepository
from course2career.user_repository import StoredUser


def _master_key() -> str:
    return base64.urlsafe_b64encode(bytes(range(32))).decode()


def _add_developer(repository: SQLiteProductRepository) -> Principal:
    repository.add(
        StoredUser(
            id="developer-1",
            username="developer",
            username_normalized="developer",
            password_hash="not-used",
            role=Role.DEVELOPER,
            plan=Plan.DEVELOPER,
            created_time="2026-07-23T00:00:00+00:00",
        )
    )
    return Principal(
        role=Role.DEVELOPER,
        plan=Plan.DEVELOPER,
        user_id="developer-1",
        username="developer",
    )


def test_cipher_encrypts_and_binds_key_to_user_and_provider() -> None:
    cipher = APIKeyCipher.from_base64_key(_master_key())

    encrypted = cipher.encrypt(
        "secret-api-key", user_id="developer-1", provider=ProviderName.OPENAI
    )

    assert b"secret-api-key" not in encrypted.ciphertext
    assert (
        cipher.decrypt(
            encrypted,
            user_id="developer-1",
            provider=ProviderName.OPENAI,
        )
        == "secret-api-key"
    )
    with pytest.raises(KeyDecryptionError):
        cipher.decrypt(
            encrypted,
            user_id="another-user",
            provider=ProviderName.OPENAI,
        )


def test_cipher_rejects_invalid_environment_key() -> None:
    with pytest.raises(KeyEncryptionConfigurationError, match="32字节"):
        APIKeyCipher.from_base64_key("invalid")


def test_service_persists_only_ciphertext_and_returns_key_to_owner(
    tmp_path: Path,
) -> None:
    repository = SQLiteProductRepository(tmp_path / "test.db")
    developer = _add_developer(repository)
    service = APIKeyService(repository, APIKeyCipher.from_base64_key(_master_key()))

    metadata = service.save_key(developer, ProviderName.DEEPSEEK, "deepseek-secret-key")

    assert metadata.provider == ProviderName.DEEPSEEK
    assert metadata.last_four == "-key"
    assert service.get_key(developer, ProviderName.DEEPSEEK) == "deepseek-secret-key"
    with sqlite3.connect(repository.database_path) as connection:
        stored = connection.execute(
            "SELECT encrypted_key FROM user_api_keys WHERE user_id = ?",
            ("developer-1",),
        ).fetchone()[0]
    assert b"deepseek-secret-key" not in stored


def test_normal_user_cannot_save_or_read_own_api_key(tmp_path: Path) -> None:
    repository = SQLiteProductRepository(tmp_path / "test.db")
    service = APIKeyService(repository, APIKeyCipher.from_base64_key(_master_key()))
    user = Principal(role=Role.USER, user_id="user-1", username="user")

    with pytest.raises(PermissionDeniedError):
        service.save_key(user, ProviderName.OPENAI, "secret-api-key")
