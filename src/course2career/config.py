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
    openai_timeout_seconds: float = 30.0
    database_path: str = "instance/course2career.db"
    key_encryption_key: str | None = field(default=None, repr=False)
    bootstrap_admin_username: str | None = None
    bootstrap_admin_password: str | None = field(default=None, repr=False)


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
        openai_timeout_seconds=max(timeout, 1.0),
        database_path=os.getenv(
            "COURSE2CAREER_DATABASE_PATH", "instance/course2career.db"
        ),
        key_encryption_key=os.getenv("COURSE2CAREER_KEY_ENCRYPTION_KEY") or None,
        bootstrap_admin_username=os.getenv("COURSE2CAREER_BOOTSTRAP_ADMIN_USERNAME")
        or None,
        bootstrap_admin_password=os.getenv("COURSE2CAREER_BOOTSTRAP_ADMIN_PASSWORD")
        or None,
    )
