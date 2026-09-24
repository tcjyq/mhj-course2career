import json
import re
import sqlite3
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4
from zoneinfo import ZoneInfo

from course2career.llm_provider import ProviderName
from course2career.models import AdaptabilityReport, AnalysisReport
from course2career.user_repository import SQLiteUserRepository


class QuotaConflictError(RuntimeError):
    """仓储检测到当前周期额度已耗尽。"""


@dataclass(frozen=True)
class AnalysisSummary:
    id: str
    job_title: str | None
    match_score: float
    created_time: str


@dataclass(frozen=True)
class StoredAnalysis:
    """属于指定用户的一份完整分析报告快照。"""

    id: str
    report: AnalysisReport | AdaptabilityReport


@dataclass(frozen=True)
class StoredAPIKey:
    user_id: str
    provider: str
    encrypted_key: bytes
    nonce: bytes
    last_four: str
    updated_time: str


@dataclass(frozen=True)
class StoredProviderProfile:
    user_id: str
    provider: str
    endpoint_id: str
    model_id: str
    created_time: str
    updated_time: str
    workspace_id: str | None = None


@dataclass(frozen=True)
class StoredBYOKMode:
    user_id: str
    byok_enabled: bool
    updated_at: str


@dataclass(frozen=True)
class AdminOverview:
    user_count: int
    today_analysis_count: int
    ai_call_count: int
    total_tokens: int
    estimated_cost: float
    unknown_cost_calls: int


@dataclass(frozen=True)
class AdminUserSummary:
    id: str
    username: str
    role: str
    plan: str
    created_time: str


class SQLiteProductRepository(SQLiteUserRepository):
    """在用户仓储之上增加AI用量和分析历史持久化。"""

    def __init__(self, database_path: str | Path) -> None:
        super().__init__(database_path)

    def reserve_ai_call(
        self,
        *,
        user_id: str | None,
        guest_session_id: str | None,
        key_mode: str,
        model: str,
        provider: str = "openai",
        daily_limit: int | None,
        created_time: datetime,
    ) -> str:
        usage_id = str(uuid4())
        local_time = created_time.astimezone(ZoneInfo("Asia/Shanghai"))
        local_day_start = local_time.replace(hour=0, minute=0, second=0, microsecond=0)
        day_start = local_day_start.astimezone(UTC)
        day_end = (local_day_start + timedelta(days=1)).astimezone(UTC)
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            if daily_limit is not None:
                used = connection.execute(
                    """
                    SELECT COUNT(*) FROM api_usage
                    WHERE user_id IS ? AND guest_session_id IS ?
                      AND key_mode = ? AND created_time >= ? AND created_time < ?
                    """,
                    (
                        user_id,
                        guest_session_id,
                        key_mode,
                        day_start.isoformat(),
                        day_end.isoformat(),
                    ),
                ).fetchone()[0]
                if used >= daily_limit:
                    raise QuotaConflictError
            connection.execute(
                """
                INSERT INTO api_usage (
                    id, user_id, guest_session_id, provider, model, key_mode,
                    input_tokens, output_tokens, cost, status, created_time
                ) VALUES (?, ?, ?, ?, ?, ?, 0, 0, 0, 'reserved', ?)
                """,
                (
                    usage_id,
                    user_id,
                    guest_session_id,
                    provider,
                    model,
                    key_mode,
                    created_time.astimezone(UTC).isoformat(),
                ),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return usage_id

    def complete_ai_call(
        self,
        usage_id: str,
        *,
        status: str,
        input_tokens: int = 0,
        output_tokens: int = 0,
        cost: float = 0,
        cost_status: str = "unknown",
        model: str | None = None,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                UPDATE api_usage
                SET status = ?, input_tokens = ?, output_tokens = ?, cost = ?,
                    cost_status = ?,
                    model = COALESCE(?, model)
                WHERE id = ?
                """,
                (
                    status,
                    input_tokens,
                    output_tokens,
                    cost,
                    cost_status,
                    model,
                    usage_id,
                ),
            )

    def count_ai_calls_today(
        self,
        *,
        user_id: str | None,
        guest_session_id: str | None,
        key_mode: str,
        created_time: datetime,
    ) -> int:
        local_time = created_time.astimezone(ZoneInfo("Asia/Shanghai"))
        local_day_start = local_time.replace(hour=0, minute=0, second=0, microsecond=0)
        day_start = local_day_start.astimezone(UTC).isoformat()
        day_end = (local_day_start + timedelta(days=1)).astimezone(UTC).isoformat()
        with self._connect() as connection:
            count = connection.execute(
                """
                SELECT COUNT(*) FROM api_usage
                WHERE user_id IS ? AND guest_session_id IS ?
                  AND key_mode = ? AND created_time >= ? AND created_time < ?
                """,
                (
                    user_id,
                    guest_session_id,
                    key_mode,
                    day_start,
                    day_end,
                ),
            ).fetchone()[0]
        return int(count)

    def add_analysis(
        self, user_id: str, report: AnalysisReport | AdaptabilityReport
    ) -> str:
        record_id = str(uuid4())
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO analysis_records (
                    id, user_id, job_title, match_score,
                    report_snapshot, created_time
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    user_id,
                    report.job_title,
                    report.overall_score,
                    report.model_dump_json(),
                    datetime.now(UTC).isoformat(),
                ),
            )
        return record_id

    def list_analyses(self, user_id: str) -> list[AnalysisSummary]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, job_title, match_score, created_time
                FROM analysis_records WHERE user_id = ?
                ORDER BY created_time DESC
                """,
                (user_id,),
            ).fetchall()
        return [
            AnalysisSummary(
                id=row["id"],
                job_title=row["job_title"],
                match_score=float(row["match_score"]),
                created_time=row["created_time"],
            )
            for row in rows
        ]

    def get_analysis(self, user_id: str, record_id: str) -> StoredAnalysis | None:
        """按用户范围读取完整报告，避免跨账号访问历史快照。"""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT id, report_snapshot
                FROM analysis_records
                WHERE id = ? AND user_id = ?
                """,
                (record_id, user_id),
            ).fetchone()
        if row is None:
            return None
        return StoredAnalysis(
            id=row["id"],
            report=_parse_report_snapshot(row["report_snapshot"]),
        )

    def system_counts(self) -> tuple[int, int, int]:
        with self._connect() as connection:
            user_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            usage_count = connection.execute(
                "SELECT COUNT(*) FROM api_usage"
            ).fetchone()[0]
            analysis_count = connection.execute(
                "SELECT COUNT(*) FROM analysis_records"
            ).fetchone()[0]
        return int(user_count), int(usage_count), int(analysis_count)

    def admin_overview(self, created_time: datetime) -> AdminOverview:
        local_time = created_time.astimezone(ZoneInfo("Asia/Shanghai"))
        local_day_start = local_time.replace(hour=0, minute=0, second=0, microsecond=0)
        day_start = local_day_start.astimezone(UTC).isoformat()
        day_end = (local_day_start + timedelta(days=1)).astimezone(UTC).isoformat()
        with self._connect() as connection:
            user_count = connection.execute("SELECT COUNT(*) FROM users").fetchone()[0]
            today_analysis_count = connection.execute(
                """
                SELECT COUNT(*) FROM analysis_records
                WHERE created_time >= ? AND created_time < ?
                """,
                (day_start, day_end),
            ).fetchone()[0]
            usage = connection.execute(
                """
                SELECT COUNT(*),
                       COALESCE(SUM(input_tokens + output_tokens), 0),
                       COALESCE(SUM(cost), 0),
                       COALESCE(SUM(CASE WHEN cost_status = 'unknown'
                           THEN 1 ELSE 0 END), 0)
                FROM api_usage
                """
            ).fetchone()
        return AdminOverview(
            user_count=int(user_count),
            today_analysis_count=int(today_analysis_count),
            ai_call_count=int(usage[0]),
            total_tokens=int(usage[1]),
            estimated_cost=float(usage[2]),
            unknown_cost_calls=int(usage[3]),
        )

    def list_users_for_admin(self) -> list[AdminUserSummary]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT id, username, role, plan, created_time
                FROM users ORDER BY created_time DESC
                """
            ).fetchall()
        return [
            AdminUserSummary(
                id=row["id"],
                username=row["username"],
                role=row["role"],
                plan=row["plan"],
                created_time=row["created_time"],
            )
            for row in rows
        ]

    def upsert_api_key(self, key: StoredAPIKey) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO user_api_keys (
                    user_id, provider, encrypted_key, nonce,
                    last_four, updated_time
                ) VALUES (?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, provider) DO UPDATE SET
                    encrypted_key = excluded.encrypted_key,
                    nonce = excluded.nonce,
                    last_four = excluded.last_four,
                    updated_time = excluded.updated_time
                """,
                (
                    key.user_id,
                    key.provider,
                    key.encrypted_key,
                    key.nonce,
                    key.last_four,
                    key.updated_time,
                ),
            )

    def get_api_key(self, user_id: str, provider: str) -> StoredAPIKey | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT user_id, provider, encrypted_key, nonce,
                       last_four, updated_time
                FROM user_api_keys WHERE user_id = ? AND provider = ?
                """,
                (user_id, provider),
            ).fetchone()
        if row is None:
            return None
        return StoredAPIKey(
            user_id=row["user_id"],
            provider=row["provider"],
            encrypted_key=bytes(row["encrypted_key"]),
            nonce=bytes(row["nonce"]),
            last_four=row["last_four"],
            updated_time=row["updated_time"],
        )

    def list_api_keys(self, user_id: str) -> list[StoredAPIKey]:
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT user_id, provider, encrypted_key, nonce,
                       last_four, updated_time
                FROM user_api_keys WHERE user_id = ? ORDER BY provider
                """,
                (user_id,),
            ).fetchall()
        return [
            StoredAPIKey(
                user_id=row["user_id"],
                provider=row["provider"],
                encrypted_key=bytes(row["encrypted_key"]),
                nonce=bytes(row["nonce"]),
                last_four=row["last_four"],
                updated_time=row["updated_time"],
            )
            for row in rows
        ]

    def delete_api_key(self, user_id: str, provider: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM user_api_keys WHERE user_id = ? AND provider = ?",
                (user_id, provider),
            )

    def upsert_provider_profile(self, profile: StoredProviderProfile) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO user_provider_profiles (
                    user_id, provider, endpoint_id, model_id,
                    created_time, updated_time, workspace_id
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(user_id, provider) DO UPDATE SET
                    endpoint_id = excluded.endpoint_id,
                    model_id = excluded.model_id,
                    updated_time = excluded.updated_time,
                    workspace_id = excluded.workspace_id
                """,
                (
                    profile.user_id,
                    profile.provider,
                    profile.endpoint_id,
                    profile.model_id,
                    profile.created_time,
                    profile.updated_time,
                    profile.workspace_id,
                ),
            )

    def get_provider_profile(
        self, user_id: str, provider: str
    ) -> StoredProviderProfile | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM user_provider_profiles "
                "WHERE user_id = ? AND provider = ?",
                (user_id, provider),
            ).fetchone()
        return StoredProviderProfile(**dict(row)) if row is not None else None

    def list_provider_profiles(self, user_id: str) -> list[StoredProviderProfile]:
        with self._connect() as connection:
            rows = connection.execute(
                "SELECT * FROM user_provider_profiles "
                "WHERE user_id = ? ORDER BY provider",
                (user_id,),
            ).fetchall()
        return [StoredProviderProfile(**dict(row)) for row in rows]

    def delete_provider_profile(self, user_id: str, provider: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "DELETE FROM user_provider_profiles WHERE user_id = ? AND provider = ?",
                (user_id, provider),
            )

    def get_byok_mode(self, user_id: str) -> StoredBYOKMode | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT user_id, byok_enabled, updated_at "
                "FROM user_byok_settings WHERE user_id = ?",
                (user_id,),
            ).fetchone()
        if row is None:
            return None
        return StoredBYOKMode(
            user_id=row["user_id"],
            byok_enabled=bool(row["byok_enabled"]),
            updated_at=row["updated_at"],
        )

    def set_byok_mode(
        self, user_id: str, enabled: bool, updated_at: str
    ) -> StoredBYOKMode:
        connection = self._connect()
        try:
            connection.execute("BEGIN IMMEDIATE")
            user = connection.execute(
                "SELECT id FROM users WHERE id = ? AND status = 'active'",
                (user_id,),
            ).fetchone()
            if user is None:
                raise LookupError("用户不存在或已停用。")
            connection.execute(
                """
                INSERT INTO user_byok_settings (user_id, byok_enabled, updated_at)
                VALUES (?, ?, ?)
                ON CONFLICT(user_id) DO UPDATE SET
                    byok_enabled = excluded.byok_enabled,
                    updated_at = excluded.updated_at
                """,
                (user_id, int(enabled), updated_at),
            )
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
        return StoredBYOKMode(user_id, enabled, updated_at)

    def _initialize_schema(self) -> None:
        super()._initialize_schema()
        with self._connect() as connection:
            connection.executescript(
                """
                BEGIN IMMEDIATE;
                CREATE TABLE IF NOT EXISTS api_usage (
                    id TEXT PRIMARY KEY,
                    user_id TEXT REFERENCES users(id) ON DELETE CASCADE,
                    guest_session_id TEXT,
                    provider TEXT NOT NULL,
                    model TEXT NOT NULL,
                    key_mode TEXT NOT NULL CHECK (key_mode IN ('system', 'user')),
                    input_tokens INTEGER NOT NULL DEFAULT 0 CHECK (input_tokens >= 0),
                    output_tokens INTEGER NOT NULL DEFAULT 0 CHECK (output_tokens >= 0),
                    cost NUMERIC NOT NULL DEFAULT 0 CHECK (cost >= 0),
                    cost_status TEXT NOT NULL DEFAULT 'unknown'
                        CHECK (cost_status IN ('estimated', 'unknown')),
                    status TEXT NOT NULL,
                    created_time TEXT NOT NULL,
                    CHECK (user_id IS NOT NULL OR guest_session_id IS NOT NULL)
                );
                CREATE INDEX IF NOT EXISTS idx_api_usage_user_time
                    ON api_usage(user_id, created_time);
                CREATE INDEX IF NOT EXISTS idx_api_usage_guest_time
                    ON api_usage(guest_session_id, created_time);

                CREATE TABLE IF NOT EXISTS analysis_records (
                    id TEXT PRIMARY KEY,
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    job_title TEXT,
                    match_score NUMERIC NOT NULL CHECK (
                        match_score >= 0 AND match_score <= 100
                    ),
                    report_snapshot TEXT NOT NULL,
                    created_time TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_analysis_user_time
                    ON analysis_records(user_id, created_time);

                CREATE TABLE IF NOT EXISTS user_api_keys (
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    provider TEXT NOT NULL CHECK (
                        provider IN (
                            'openai', 'deepseek', 'bailian', 'openrouter',
                            'siliconflow', 'moonshot', 'zhipu', 'minimax',
                            'gemini', 'anthropic'
                        )
                    ),
                    encrypted_key BLOB NOT NULL,
                    nonce BLOB NOT NULL CHECK (length(nonce) = 12),
                    last_four TEXT NOT NULL,
                    updated_time TEXT NOT NULL,
                    PRIMARY KEY (user_id, provider)
                );

                CREATE TABLE IF NOT EXISTS user_provider_profiles (
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    provider TEXT NOT NULL,
                    endpoint_id TEXT NOT NULL,
                    model_id TEXT NOT NULL,
                    created_time TEXT NOT NULL,
                    updated_time TEXT NOT NULL,
                    workspace_id TEXT,
                    PRIMARY KEY (user_id, provider)
                );

                CREATE TABLE IF NOT EXISTS user_byok_settings (
                    user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    byok_enabled INTEGER NOT NULL DEFAULT 0
                        CHECK (byok_enabled IN (0, 1)),
                    updated_at TEXT NOT NULL
                );
                """
            )
            try:
                columns = {
                    row["name"]
                    for row in connection.execute("PRAGMA table_info(api_usage)")
                }
                if "cost_status" not in columns:
                    connection.execute(
                        "ALTER TABLE api_usage ADD COLUMN cost_status TEXT "
                        "NOT NULL DEFAULT 'unknown' "
                        "CHECK (cost_status IN ('estimated', 'unknown'))"
                    )
                profile_columns = {
                    row["name"]
                    for row in connection.execute(
                        "PRAGMA table_info(user_provider_profiles)"
                    )
                }
                if "workspace_id" not in profile_columns:
                    connection.execute(
                        "ALTER TABLE user_provider_profiles "
                        "ADD COLUMN workspace_id TEXT"
                    )
                self._extend_api_key_provider_constraint(connection)
                connection.commit()
            except Exception:
                connection.rollback()
                raise

    @staticmethod
    def _extend_api_key_provider_constraint(connection: sqlite3.Connection) -> None:
        """只在旧表约束存在时重建表，原样复制密文与绑定字段。"""
        schema = connection.execute(
            "SELECT sql FROM sqlite_master "
            "WHERE type = 'table' AND name = 'user_api_keys'"
        ).fetchone()[0]
        match = re.search(r"provider\s+IN\s*\(([^)]*)\)", schema, re.I)
        if match is None:
            raise RuntimeError("无法识别 API Key 表约束，已停止自动升级。")
        actual = set(re.findall(r"'([a-z0-9_]+)'", match.group(1)))
        target = {provider.value for provider in ProviderName}
        if actual == target:
            return
        if actual not in (
            {"openai", "deepseek"},
            {"openai", "deepseek", "bailian", "openrouter"},
        ):
            raise RuntimeError("无法识别 API Key 表约束，已停止自动升级。")
        connection.execute(
            """
                CREATE TABLE user_api_keys_c08 (
                    user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
                    provider TEXT NOT NULL CHECK (
                        provider IN (
                            'openai', 'deepseek', 'bailian', 'openrouter',
                            'siliconflow', 'moonshot', 'zhipu', 'minimax',
                            'gemini', 'anthropic'
                        )
                    ),
                    encrypted_key BLOB NOT NULL,
                    nonce BLOB NOT NULL CHECK (length(nonce) = 12),
                    last_four TEXT NOT NULL,
                    updated_time TEXT NOT NULL,
                    PRIMARY KEY (user_id, provider)
                )
                """
        )
        connection.execute(
            """
                INSERT INTO user_api_keys_c08
                    (user_id, provider, encrypted_key, nonce, last_four, updated_time)
                SELECT user_id, provider, encrypted_key, nonce, last_four, updated_time
                FROM user_api_keys
                """
        )
        connection.execute("DROP TABLE user_api_keys")
        connection.execute("ALTER TABLE user_api_keys_c08 RENAME TO user_api_keys")


def _parse_report_snapshot(snapshot: str) -> AnalysisReport | AdaptabilityReport:
    """兼容早期技能报告与当前 v2.1 岗位适配度报告。"""
    payload = json.loads(snapshot)
    if payload.get("scoring_version") == "2.1":
        return AdaptabilityReport.model_validate(payload)
    return AnalysisReport.model_validate(payload)
