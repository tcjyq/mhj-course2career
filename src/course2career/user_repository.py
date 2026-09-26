import sqlite3
from contextlib import nullcontext
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from course2career.database_backend import DatabaseBackend
from course2career.permissions import Plan, Role


@dataclass(frozen=True)
class StoredUser:
    id: str
    username: str
    username_normalized: str
    password_hash: str
    role: Role
    plan: Plan
    created_time: str
    session_version: int = 1
    status: str = "active"


@dataclass(frozen=True)
class StoredAuthSession:
    id: str
    user_id: str
    token_hash: str
    session_version: int
    created_time: str
    expires_time: str
    revoked_time: str | None = None


class SQLiteUserRepository:
    """SQLite 用户仓储；查询全部使用参数化语句。"""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.backend = DatabaseBackend(database_path=self.database_path)
        from course2career.database_migrations import migrate_sqlite

        migrate_sqlite(self, target=1)

    def add(self, user: StoredUser) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO users (
                    id, username, username_normalized, password_hash,
                    role, plan, created_time, session_version, status
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user.id,
                    user.username,
                    user.username_normalized,
                    user.password_hash,
                    user.role.value,
                    Plan(user.plan).value,
                    user.created_time,
                    user.session_version,
                    user.status,
                ),
            )

    def find_by_normalized_username(self, username: str) -> StoredUser | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE username_normalized = ?", (username,)
            ).fetchone()
        if row is None:
            return None
        return _row_to_user(row)

    def count_users(self) -> int:
        with self._connect() as connection:
            return int(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0])

    def find_by_id(self, user_id: str) -> StoredUser | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE id = ?", (user_id,)
            ).fetchone()
        if row is None:
            return None
        return _row_to_user(row)

    def find_admin(self) -> StoredUser | None:
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM users
                WHERE role = 'admin' AND plan = 'admin'
                ORDER BY created_time, id
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            return None
        return _row_to_user(row)

    def update_password_hash(
        self, user_id: str, password_hash: str
    ) -> StoredUser | None:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE users
                SET password_hash = ?, session_version = session_version + 1
                WHERE id = ?
                """,
                (password_hash, user_id),
            )
        if cursor.rowcount != 1:
            return None
        return self.find_by_id(user_id)

    def count_recent_failed_logins(
        self,
        scope_id: str,
        username_normalized: str,
        since: datetime,
    ) -> int:
        with self._connect() as connection:
            count = connection.execute(
                """
                SELECT COUNT(*) FROM login_attempts
                WHERE scope_id = ? AND username_normalized = ?
                  AND attempted_time >= ?
                """,
                (scope_id, username_normalized, since.isoformat()),
            ).fetchone()[0]
        return int(count)

    def record_failed_login(
        self,
        scope_id: str,
        username_normalized: str,
        attempted_time: datetime,
    ) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO login_attempts (
                    scope_id, username_normalized, attempted_time
                ) VALUES (?, ?, ?)
                """,
                (scope_id, username_normalized, attempted_time.isoformat()),
            )

    def clear_failed_logins(self, scope_id: str, username_normalized: str) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                DELETE FROM login_attempts
                WHERE scope_id = ? AND username_normalized = ?
                """,
                (scope_id, username_normalized),
            )

    def update_membership(self, user_id: str, role: Role, plan: Plan) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                """
                UPDATE users
                SET role = ?, plan = ?, session_version = session_version + 1
                WHERE id = ?
                """,
                (role.value, plan.value, user_id),
            )
        return cursor.rowcount == 1

    def add_auth_session(self, session: StoredAuthSession) -> None:
        with self._connect() as connection:
            connection.execute(
                "INSERT INTO auth_sessions (id, user_id, token_hash, "
                "session_version, created_time, expires_time, revoked_time) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    session.id,
                    session.user_id,
                    session.token_hash,
                    session.session_version,
                    session.created_time,
                    session.expires_time,
                    session.revoked_time,
                ),
            )

    def find_auth_session(self, token_hash: str) -> StoredAuthSession | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT id, user_id, token_hash, session_version, "
                "created_time, expires_time, revoked_time "
                "FROM auth_sessions WHERE token_hash = ?",
                (token_hash,),
            ).fetchone()
        return StoredAuthSession(**dict(row)) if row is not None else None

    def revoke_auth_session(self, token_hash: str, revoked_time: str) -> None:
        with self._connect() as connection:
            connection.execute(
                "UPDATE auth_sessions SET revoked_time = ? "
                "WHERE token_hash = ? AND revoked_time IS NULL",
                (revoked_time, token_hash),
            )

    def _connect(self) -> sqlite3.Connection:
        return self.backend.connect()

    def _initialize_schema(self, migration_connection=None) -> None:
        from course2career.database_migrations import execute_sqlite_statements

        with (
            nullcontext(migration_connection)
            if migration_connection
            else self._connect() as connection
        ):
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS users (
                    id TEXT PRIMARY KEY,
                    username TEXT NOT NULL,
                    username_normalized TEXT NOT NULL UNIQUE,
                    password_hash TEXT NOT NULL,
                    role TEXT NOT NULL CHECK (
                        role IN ('user', 'developer', 'admin')
                    ),
                    plan TEXT NOT NULL DEFAULT 'free' CHECK (
                        plan IN ('free', 'pro', 'developer', 'admin')
                    ),
                    created_time TEXT NOT NULL,
                    session_version INTEGER NOT NULL DEFAULT 1,
                    status TEXT NOT NULL DEFAULT 'active' CHECK (
                        status IN ('active', 'disabled')
                    )
                )
                """
            )
            columns = {
                row["name"]
                for row in connection.execute("PRAGMA table_info(users)").fetchall()
            }
            if "session_version" not in columns:
                connection.execute(
                    """
                    ALTER TABLE users
                    ADD COLUMN session_version INTEGER NOT NULL DEFAULT 1
                    """
                )
            if "status" not in columns:
                connection.execute(
                    """
                    ALTER TABLE users
                    ADD COLUMN status TEXT NOT NULL DEFAULT 'active'
                    """
                )
            connection.execute(
                """
                UPDATE users SET plan = CASE role
                    WHEN 'developer' THEN 'developer'
                    WHEN 'admin' THEN 'admin'
                    ELSE plan
                END
                WHERE plan = 'free' AND role IN ('developer', 'admin')
                """
            )
            execute_sqlite_statements(
                connection,
                """
                CREATE TABLE IF NOT EXISTS login_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    scope_id TEXT NOT NULL,
                    username_normalized TEXT NOT NULL,
                    attempted_time TEXT NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_login_attempt_scope_user_time
                    ON login_attempts(
                        scope_id, username_normalized, attempted_time
                    );
                """,
            )


def _row_to_user(row: sqlite3.Row) -> StoredUser:
    return StoredUser(
        id=row["id"],
        username=row["username"],
        username_normalized=row["username_normalized"],
        password_hash=row["password_hash"],
        role=Role(row["role"]),
        plan=Plan(row["plan"]),
        created_time=row["created_time"],
        session_version=int(row["session_version"]),
        status=row["status"],
    )
