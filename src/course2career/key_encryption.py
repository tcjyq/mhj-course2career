import base64
import binascii
import os
from dataclasses import dataclass

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from course2career.llm_provider import ProviderName


class KeyEncryptionConfigurationError(ValueError):
    """密钥加密主密钥缺失或格式不正确。"""


class KeyDecryptionError(RuntimeError):
    """密文损坏、绑定信息不匹配或主密钥错误。"""


@dataclass(frozen=True)
class EncryptedSecret:
    ciphertext: bytes
    nonce: bytes


class APIKeyCipher:
    """使用AES-256-GCM加密API Key，并绑定用户和供应商。"""

    def __init__(self, master_key: bytes) -> None:
        if len(master_key) != 32:
            raise KeyEncryptionConfigurationError("API Key加密主密钥必须为32字节。")
        self._cipher = AESGCM(master_key)

    @classmethod
    def from_base64_key(cls, encoded_key: str | None) -> "APIKeyCipher":
        if not encoded_key:
            raise KeyEncryptionConfigurationError(
                "未配置COURSE2CAREER_KEY_ENCRYPTION_KEY。"
            )
        try:
            key = base64.b64decode(
                encoded_key.encode("ascii"), altchars=b"-_", validate=True
            )
        except (UnicodeEncodeError, binascii.Error) as exc:
            raise KeyEncryptionConfigurationError(
                "API Key加密主密钥必须是Base64编码的32字节值。"
            ) from exc
        return cls(key)

    def encrypt(
        self, plaintext: str, *, user_id: str, provider: ProviderName
    ) -> EncryptedSecret:
        nonce = os.urandom(12)
        ciphertext = self._cipher.encrypt(
            nonce,
            plaintext.encode("utf-8"),
            _associated_data(user_id, provider),
        )
        return EncryptedSecret(ciphertext=ciphertext, nonce=nonce)

    def decrypt(
        self,
        encrypted: EncryptedSecret,
        *,
        user_id: str,
        provider: ProviderName,
    ) -> str:
        try:
            plaintext = self._cipher.decrypt(
                encrypted.nonce,
                encrypted.ciphertext,
                _associated_data(user_id, provider),
            )
            return plaintext.decode("utf-8")
        except (InvalidTag, UnicodeDecodeError) as exc:
            raise KeyDecryptionError("无法解密已保存的API Key。") from exc


def _associated_data(user_id: str, provider: ProviderName) -> bytes:
    return f"course2career:{user_id}:{provider.value}".encode()
