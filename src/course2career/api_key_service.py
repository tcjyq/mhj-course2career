from datetime import UTC, datetime

from pydantic import BaseModel, ConfigDict

from course2career.key_encryption import APIKeyCipher, EncryptedSecret
from course2career.llm_provider import ProviderName
from course2career.permissions import Permission, Principal, authorize
from course2career.product_repository import (
    SQLiteProductRepository,
    StoredAPIKey,
)


class APIKeyNotFoundError(LookupError):
    """当前用户没有保存指定供应商的API Key。"""


class APIKeyMetadata(BaseModel):
    model_config = ConfigDict(frozen=True)

    provider: ProviderName
    last_four: str
    updated_time: str


class APIKeyService:
    """加密保存并按当前用户身份解析开发者API Key。"""

    def __init__(
        self, repository: SQLiteProductRepository, cipher: APIKeyCipher
    ) -> None:
        self.repository = repository
        self.cipher = cipher

    def save_key(
        self,
        principal: Principal,
        provider: ProviderName,
        api_key: str,
    ) -> APIKeyMetadata:
        authorize(principal, Permission.CONFIGURE_OWN_API_KEY)
        user_id = _require_user_id(principal)
        cleaned_key = api_key.strip()
        if not 8 <= len(cleaned_key) <= 512:
            raise ValueError("API Key长度无效。")
        encrypted = self.cipher.encrypt(cleaned_key, user_id=user_id, provider=provider)
        updated_time = datetime.now(UTC).isoformat()
        self.repository.upsert_api_key(
            StoredAPIKey(
                user_id=user_id,
                provider=provider.value,
                encrypted_key=encrypted.ciphertext,
                nonce=encrypted.nonce,
                last_four=cleaned_key[-4:],
                updated_time=updated_time,
            )
        )
        return APIKeyMetadata(
            provider=provider,
            last_four=cleaned_key[-4:],
            updated_time=updated_time,
        )

    def get_key(self, principal: Principal, provider: ProviderName) -> str:
        authorize(principal, Permission.USE_OWN_API_KEY)
        user_id = _require_user_id(principal)
        stored = self.repository.get_api_key(user_id, provider.value)
        if stored is None:
            raise APIKeyNotFoundError("尚未保存该模型供应商的API Key。")
        return self.cipher.decrypt(
            EncryptedSecret(
                ciphertext=stored.encrypted_key,
                nonce=stored.nonce,
            ),
            user_id=user_id,
            provider=provider,
        )

    def list_keys(self, principal: Principal) -> list[APIKeyMetadata]:
        authorize(principal, Permission.CONFIGURE_OWN_API_KEY)
        user_id = _require_user_id(principal)
        return [
            APIKeyMetadata(
                provider=ProviderName(stored.provider),
                last_four=stored.last_four,
                updated_time=stored.updated_time,
            )
            for stored in self.repository.list_api_keys(user_id)
        ]

    def delete_key(self, principal: Principal, provider: ProviderName) -> None:
        authorize(principal, Permission.CONFIGURE_OWN_API_KEY)
        self.repository.delete_api_key(_require_user_id(principal), provider.value)


def _require_user_id(principal: Principal) -> str:
    if principal.user_id is None:
        raise PermissionError("登录后才能管理API Key。")
    return principal.user_id
