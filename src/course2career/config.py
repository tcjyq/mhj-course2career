import os
from dataclasses import dataclass, field

from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    """应用运行配置；敏感值只从环境变量读取。"""

    openai_api_key: str | None = field(default=None, repr=False)
    openai_model: str = "gpt-5.6-luna"
    deepseek_api_key: str | None = field(default=None, repr=False)
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_model_mode: str = "auto_safe"
    deepseek_model_preference: tuple[str, ...] = (
        "deepseek-v4-flash",
        "deepseek-v4-pro",
    )
    deepseek_model_cache_seconds: int = 1800
    deepseek_model_stale_seconds: int = 86400
    deepseek_max_output_tokens: int = 1500
    system_ai_enabled: bool = True
    openai_input_cost_per_million: float = 0.0
    openai_output_cost_per_million: float = 0.0
    deepseek_input_cost_per_million: float = 0.0
    deepseek_output_cost_per_million: float = 0.0
    openai_timeout_seconds: float = 30.0
    database_path: str = "instance/course2career.db"
    key_encryption_key: str | None = field(default=None, repr=False)
    admin_username: str | None = None
    admin_password: str | None = field(default=None, repr=False)
    admin_password_hash: str | None = field(default=None, repr=False)


def load_settings() -> Settings:
    load_dotenv()
    timeout_value = os.getenv("OPENAI_TIMEOUT_SECONDS", "30")
    try:
        timeout = float(timeout_value)
    except ValueError:
        timeout = 30.0
    raw_model_mode = os.getenv("DEEPSEEK_MODEL_MODE")
    model_mode = (
        "auto_safe" if raw_model_mode is None else raw_model_mode.strip().lower()
    )
    if model_mode not in {"pinned", "auto_safe"}:
        model_mode = "pinned"
    preference = _csv_env(
        "DEEPSEEK_MODEL_PREFERENCE",
        ("deepseek-v4-flash", "deepseek-v4-pro"),
    )
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY") or None,
        deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
        deepseek_model_mode=model_mode,
        deepseek_model_preference=preference,
        deepseek_model_cache_seconds=_positive_int_env(
            "DEEPSEEK_MODEL_CACHE_SECONDS", 1800
        ),
        deepseek_model_stale_seconds=_positive_int_env(
            "DEEPSEEK_MODEL_STALE_SECONDS", 86400
        ),
        deepseek_max_output_tokens=_positive_int_env(
            "DEEPSEEK_MAX_OUTPUT_TOKENS", 1500
        ),
        system_ai_enabled=_bool_env("SYSTEM_AI_ENABLED", True),
        openai_input_cost_per_million=_nonnegative_float_env(
            "OPENAI_INPUT_COST_PER_MILLION"
        ),
        openai_output_cost_per_million=_nonnegative_float_env(
            "OPENAI_OUTPUT_COST_PER_MILLION"
        ),
        deepseek_input_cost_per_million=_nonnegative_float_env(
            "DEEPSEEK_INPUT_COST_PER_MILLION"
        ),
        deepseek_output_cost_per_million=_nonnegative_float_env(
            "DEEPSEEK_OUTPUT_COST_PER_MILLION"
        ),
        openai_timeout_seconds=max(timeout, 1.0),
        database_path=os.getenv(
            "COURSE2CAREER_DATABASE_PATH", "instance/course2career.db"
        ),
        key_encryption_key=os.getenv("COURSE2CAREER_KEY_ENCRYPTION_KEY") or None,
        admin_username=os.getenv("ADMIN_USERNAME") or None,
        admin_password=os.getenv("ADMIN_PASSWORD") or None,
        admin_password_hash=os.getenv("ADMIN_PASSWORD_HASH") or None,
    )


def _nonnegative_float_env(name: str) -> float:
    try:
        return max(float(os.getenv(name, "0")), 0.0)
    except ValueError:
        return 0.0


def _positive_int_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except ValueError:
        return default
    return value if value > 0 else default


def _bool_env(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    return default


def _csv_env(name: str, default: tuple[str, ...]) -> tuple[str, ...]:
    values = tuple(
        dict.fromkeys(
            item.strip() for item in os.getenv(name, "").split(",") if item.strip()
        )
    )
    return values or default
