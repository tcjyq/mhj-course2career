import hashlib
import hmac
import secrets

SCRYPT_N = 2**14
SCRYPT_R = 8
SCRYPT_P = 1
KEY_LENGTH = 64
SALT_LENGTH = 16


def hash_password(password: str) -> str:
    """使用带随机盐的 scrypt 生成不可逆密码哈希。"""

    salt = secrets.token_bytes(SALT_LENGTH)
    derived_key = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=SCRYPT_N,
        r=SCRYPT_R,
        p=SCRYPT_P,
        dklen=KEY_LENGTH,
    )
    return f"scrypt${SCRYPT_N}${SCRYPT_R}${SCRYPT_P}${salt.hex()}${derived_key.hex()}"


def verify_password(password: str, encoded_hash: str) -> bool:
    """校验密码；损坏或未知格式一律返回失败。"""

    parsed_hash = _parse_supported_hash(encoded_hash)
    if parsed_hash is None:
        return False
    salt, expected_key = parsed_hash
    try:
        actual_key = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=SCRYPT_N,
            r=SCRYPT_R,
            p=SCRYPT_P,
            dklen=len(expected_key),
        )
    except (TypeError, ValueError):
        return False
    return hmac.compare_digest(actual_key, expected_key)


def is_supported_password_hash(encoded_hash: str) -> bool:
    """确认哈希格式和计算参数均为当前应用支持的安全配置。"""

    return _parse_supported_hash(encoded_hash) is not None


def _parse_supported_hash(encoded_hash: str) -> tuple[bytes, bytes] | None:
    try:
        algorithm, n, r, p, salt_hex, key_hex = encoded_hash.split("$")
        parameters = (int(n), int(r), int(p))
        salt = bytes.fromhex(salt_hex)
        expected_key = bytes.fromhex(key_hex)
    except (AttributeError, TypeError, ValueError):
        return None
    if (
        algorithm != "scrypt"
        or parameters != (SCRYPT_N, SCRYPT_R, SCRYPT_P)
        or len(salt) != SALT_LENGTH
        or len(expected_key) != KEY_LENGTH
    ):
        return None
    return salt, expected_key
