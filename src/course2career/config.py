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
    return Settings(
        openai_api_key=os.getenv("OPENAI_API_KEY") or None,
        openai_model=os.getenv("OPENAI_MODEL", "gpt-5.6-luna"),
        deepseek_api_key=os.getenv("DEEPSEEK_API_KEY") or None,
        deepseek_model=os.getenv("DEEPSEEK_MODEL", "deepseek-v4-flash"),
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
