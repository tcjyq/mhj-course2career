"""Synthetic proof on two empty remote PostgreSQL test databases.

Credentials are read from local environment and never printed or passed as
command-line arguments. This script refuses databases containing user tables.
"""

import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from psycopg.conninfo import conninfo_to_dict

from course2career.access_services import AIUsageService
from course2career.api_key_service import APIKeyService
from course2career.auth_service import AuthService
from course2career.byok_mode import BYOKModeService
from course2career.database_backend import DatabaseBackend
from course2career.database_migrations import schema_version
from course2career.key_encryption import APIKeyCipher, KeyDecryptionError
from course2career.llm_provider import LLMUsage, ProviderName
from course2career.models import AnalysisReport
from course2career.postgres_repository import PostgresProductRepository
from course2career.provider_profile import ProviderProfileService

TABLES = (
    "users",
    "login_attempts",
    "api_usage",
    "analysis_records",
    "user_api_keys",
    "user_provider_profiles",
    "user_byok_settings",
    "schema_migrations",
)
SYNTHETIC_USERNAME = "c08-d1-fixture"
SYNTHETIC_PASSWORD = "synthetic-test-password-123"
SYNTHETIC_KEY = "synthetic-test-api-key-123"


def _empty_database(url: str) -> None:
    with DatabaseBackend(url=url).connect() as connection:
        count = connection.execute(
            "SELECT COUNT(*) FROM information_schema.tables "
            "WHERE table_schema = current_schema() AND table_type = 'BASE TABLE'"
        ).fetchone()[0]
    if count:
        raise RuntimeError("测试库已有表；必须使用全新空库，未修改任何现有数据。")


def _counts(repo: PostgresProductRepository) -> dict[str, int]:
    with repo._connect() as connection:
        return {
            table: int(
                connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
            )
            for table in TABLES
        }


def _client_environment(url: str) -> dict[str, str]:
    info = conninfo_to_dict(url)
    if not all(info.get(field) for field in ("host", "user", "dbname")):
        raise RuntimeError("测试数据库 URL 必须明确主机、用户和数据库名。")
    env = {key: value for key, value in os.environ.items() if not key.startswith("PG")}
    mapping = {
        "host": "PGHOST",
        "port": "PGPORT",
        "user": "PGUSER",
        "password": "PGPASSWORD",
        "dbname": "PGDATABASE",
        "sslmode": "PGSSLMODE",
        "sslrootcert": "PGSSLROOTCERT",
    }
    for field, name in mapping.items():
        if field in info:
            env[name] = str(info[field])
    return env


def _run_client(command: list[str], env: dict[str, str]) -> None:
    try:
        subprocess.run(
            command,
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
            timeout=120,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        raise RuntimeError(
            "PostgreSQL 备份或恢复失败；请在本机核对客户端版本和权限。"
        ) from None


def _verify_key(repo: PostgresProductRepository, cipher: APIKeyCipher) -> None:
    principal = AuthService(repo).authenticate(SYNTHETIC_USERNAME, SYNTHETIC_PASSWORD)
    assert principal.byok_enabled
    assert APIKeyService(repo, cipher).get_key(principal, ProviderName.DEEPSEEK) == (
        SYNTHETIC_KEY
    )
    before = repo.get_api_key(principal.user_id, ProviderName.DEEPSEEK.value)
    try:
        APIKeyService(repo, APIKeyCipher(os.urandom(32))).get_key(
            principal, ProviderName.DEEPSEEK
        )
    except KeyDecryptionError:
        pass
    else:
        raise AssertionError("错误主密钥意外解密成功。")
    assert repo.get_api_key(principal.user_id, ProviderName.DEEPSEEK.value) == before


def seed_and_verify(url: str, cipher: APIKeyCipher) -> dict[str, int]:
    _empty_database(url)
    repo = PostgresProductRepository(url)
    principal = AuthService(repo).register(SYNTHETIC_USERNAME, SYNTHETIC_PASSWORD)
    BYOKModeService(repo).set_enabled(principal, True)
    principal = AuthService(repo).refresh_principal(principal)
    APIKeyService(repo, cipher).save_key(
        principal, ProviderName.DEEPSEEK, SYNTHETIC_KEY
    )
    ProviderProfileService(repo).save(
        principal, ProviderName.DEEPSEEK, "global", "deepseek-flash"
    )
    repo.add_analysis(principal.user_id, AnalysisReport(overall_score=75))
    call_id = AIUsageService(repo).start_call(
        principal, "user", "deepseek-flash", provider="deepseek"
    )
    AIUsageService(repo).complete_call(
        call_id,
        success=True,
        usage=LLMUsage(input_tokens=11, output_tokens=7, model="deepseek-flash"),
    )
    reopened = PostgresProductRepository(url)
    _verify_key(reopened, cipher)
    assert reopened.list_analyses(principal.user_id)
    assert schema_version(reopened.backend) == 2
    return _counts(reopened)


def backup_restore(
    source_url: str, restore_url: str, cipher: APIKeyCipher
) -> dict[str, int]:
    source_info = conninfo_to_dict(source_url)
    restore_info = conninfo_to_dict(restore_url)
    identity = ("host", "port", "dbname")
    if tuple(source_info.get(k) for k in identity) == tuple(
        restore_info.get(k) for k in identity
    ):
        raise RuntimeError("源库与恢复目标不能相同。")
    _empty_database(restore_url)
    for binary in ("pg_dump", "pg_restore"):
        if not shutil.which(binary):
            raise RuntimeError("本机缺少 pg_dump 或 pg_restore。")
    source = PostgresProductRepository(source_url)
    _verify_key(source, cipher)
    expected = _counts(source)
    if expected != {
        "users": 1,
        "login_attempts": 0,
        "api_usage": 1,
        "analysis_records": 1,
        "user_api_keys": 1,
        "user_provider_profiles": 1,
        "user_byok_settings": 1,
        "schema_migrations": 2,
    }:
        raise RuntimeError("源库不符合纯合成数据行数；拒绝备份。")
    temp_root = Path("D:/codex_study/_tmp") if os.name == "nt" else Path.cwd()
    temp_root.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=temp_root) as temp_dir:
        backup_path = Path(temp_dir) / "c08-d1-synthetic.dump"
        _run_client(
            [
                "pg_dump",
                "--format=custom",
                "--no-owner",
                "--no-acl",
                "--file",
                str(backup_path),
            ],
            _client_environment(source_url),
        )
        if not backup_path.is_file() or backup_path.stat().st_size == 0:
            raise RuntimeError("备份文件为空。")
        _run_client(
            [
                "pg_restore",
                "--no-owner",
                "--no-acl",
                "--exit-on-error",
                "--dbname",
                restore_info["dbname"],
                str(backup_path),
            ],
            _client_environment(restore_url),
        )
    restored = PostgresProductRepository(restore_url)
    assert _counts(restored) == expected
    _verify_key(restored, cipher)
    return expected


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--restore-only", action="store_true")
    parser.add_argument("--seed-only", action="store_true")
    args = parser.parse_args()
    if args.seed_only and args.restore_only:
        parser.error("只能选择一种模式。")
    source_url = os.getenv("C2C_TEST_DATABASE_URL")
    restore_url = os.getenv("C2C_TEST_RESTORE_DATABASE_URL")
    master_key = os.getenv("COURSE2CAREER_KEY_ENCRYPTION_KEY")
    if not source_url or not master_key or (not args.seed_only and not restore_url):
        parser.error("缺少本地测试库或测试主密钥环境配置。")
    cipher = APIKeyCipher.from_base64_key(master_key)
    if not args.restore_only:
        counts = seed_and_verify(source_url, cipher)
        print("Remote PostgreSQL synthetic reconnect: PASS", counts)
    if not args.seed_only:
        counts = backup_restore(source_url, restore_url, cipher)
        print("Backup, restore and decrypt-after-restore: PASS", counts)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        print(
            "Remote PostgreSQL 验证失败；请在本机检查配置和测试库状态。",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
