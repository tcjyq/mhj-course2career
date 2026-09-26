"""Copy a reviewed SQLite snapshot into an empty PostgreSQL database."""

import os
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from urllib.parse import quote

from course2career.postgres_repository import PostgresProductRepository
from course2career.product_repository import SQLiteProductRepository

TABLES = (
    "users",
    "login_attempts",
    "api_usage",
    "analysis_records",
    "user_api_keys",
    "user_provider_profiles",
    "user_byok_settings",
)
COLUMNS = {
    "users": (
        "id",
        "username",
        "username_normalized",
        "password_hash",
        "role",
        "plan",
        "created_time",
        "session_version",
        "status",
    ),
    "login_attempts": ("id", "scope_id", "username_normalized", "attempted_time"),
    "api_usage": (
        "id",
        "user_id",
        "guest_session_id",
        "provider",
        "model",
        "key_mode",
        "input_tokens",
        "output_tokens",
        "cost",
        "cost_status",
        "status",
        "created_time",
    ),
    "analysis_records": (
        "id",
        "user_id",
        "job_title",
        "match_score",
        "report_snapshot",
        "created_time",
    ),
    "user_api_keys": (
        "user_id",
        "provider",
        "encrypted_key",
        "nonce",
        "last_four",
        "updated_time",
    ),
    "user_provider_profiles": (
        "user_id",
        "provider",
        "endpoint_id",
        "model_id",
        "created_time",
        "updated_time",
        "workspace_id",
    ),
    "user_byok_settings": ("user_id", "byok_enabled", "updated_at"),
}


def prepare_sqlite_copy(source_path: Path, copy_path: Path) -> None:
    """Upgrade an isolated copy while keeping the reviewed source read-only."""
    source_uri = f"file:{quote(source_path.resolve().as_posix(), safe='/:')}?mode=ro"
    with (
        closing(sqlite3.connect(source_uri, uri=True)) as original,
        closing(sqlite3.connect(copy_path)) as copy,
    ):
        original.backup(copy)
    SQLiteProductRepository(copy_path)


def copy_sqlite_to_postgres(
    source_path: str | Path,
    database_url: str,
    *,
    allow_insecure_local_test: bool = False,
) -> dict[str, int]:
    """Copy all durable tables in one target transaction; never print row values."""
    path = Path(source_path)
    if not path.is_file():
        raise FileNotFoundError("SQLite 源数据库不存在。")
    target = PostgresProductRepository(
        database_url, allow_insecure_local_test=allow_insecure_local_test
    )
    local_temp = Path("D:/codex_study/_tmp") if os.name == "nt" else Path.cwd()
    local_temp.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    with tempfile.TemporaryDirectory(dir=local_temp) as temp_dir:
        copy_path = Path(temp_dir) / "source-copy.db"
        prepare_sqlite_copy(path, copy_path)
        with (
            closing(sqlite3.connect(copy_path)) as source,
            target._connect() as destination,
        ):
            source.row_factory = sqlite3.Row
            if any(
                destination.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
                for table in TABLES
            ):
                raise RuntimeError("目标数据库不为空；已拒绝合并或覆盖。")
            for table in TABLES:
                columns = COLUMNS[table]
                names = ", ".join(columns)
                rows = source.execute(f"SELECT {names} FROM {table}").fetchall()
                counts[table] = len(rows)
                markers = ", ".join("?" for _ in columns)
                sql = f"INSERT INTO {table} ({names}) VALUES ({markers})"
                for row in rows:
                    destination.execute(sql, tuple(row))
            if counts["login_attempts"]:
                destination.execute(
                    "SELECT setval(pg_get_serial_sequence('login_attempts', 'id'), "
                    "(SELECT MAX(id) FROM login_attempts))"
                )
    return counts
