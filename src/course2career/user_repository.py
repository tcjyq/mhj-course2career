import sqlite3
from dataclasses import dataclass
from pathlib import Path

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


class SQLiteUserRepository:
    """SQLite 用户仓储；查询全部使用参数化语句。"""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = Path(database_path)
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialize_schema()

    def add(self, user: StoredUser) -> None:
        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO users (
                    id, username, username_normalized, password_hash,
                    role, plan, created_time
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    user.id,
                    user.username,
                    user.username_normalized,
                    user.password_hash,
                    user.role.value,
                    Plan(user.plan).value,
                    user.created_time,
                ),
            )

    def find_by_normalized_username(self, username: str) -> StoredUser | None:
        with self._connect() as connection:
            row = connection.execute(
                "SELECT * FROM users WHERE username_normalized = ?", (username,)
            ).fetchone()
        if row is None:
            return None
        return StoredUser(
            id=row["id"],
            username=row["username"],
            username_normalized=row["username_normalized"],
            password_hash=row["password_hash"],
            role=Role(row["role"]),
            plan=Plan(row["plan"]),
            created_time=row["created_time"],
        )

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
        return StoredUser(
            id=row["id"],
            username=row["username"],
            username_normalized=row["username_normalized"],
            password_hash=row["password_hash"],
            role=Role(row["role"]),
            plan=Plan(row["plan"]),
            created_time=row["created_time"],
        )

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
        return StoredUser(
            id=row["id"],
            username=row["username"],
            username_normalized=row["username_normalized"],
            password_hash=row["password_hash"],
            role=Role(row["role"]),
            plan=Plan(row["plan"]),
            created_time=row["created_time"],
        )

    def update_membership(self, user_id: str, role: Role, plan: Plan) -> bool:
        with self._connect() as connection:
            cursor = connection.execute(
                "UPDATE users SET role = ?, plan = ? WHERE id = ?",
                (role.value, plan.value, user_id),
            )
        return cursor.rowcount == 1

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize_schema(self) -> None:
        with self._connect() as connection:
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
                    created_time TEXT NOT NULL
                )
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
