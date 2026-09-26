"""Small DB boundary shared by the existing repository SQL on SQLite and PostgreSQL."""

import sqlite3
from pathlib import Path
from urllib.parse import parse_qs, urlsplit


class DatabaseConfigurationError(ValueError):
    """A production database setting cannot safely provide durable storage."""


class DatabaseUnavailableError(RuntimeError):
    """The persistent database cannot be reached; details are deliberately hidden."""


class _Row(dict):
    def __getitem__(self, key):
        if isinstance(key, int):
            return tuple(self.values())[key]
        return super().__getitem__(key)


class _Cursor:
    def __init__(self, cursor):
        self.cursor = cursor

    @property
    def rowcount(self):
        return self.cursor.rowcount

    def fetchone(self):
        row = self.cursor.fetchone()
        return _Row(row) if row is not None else None

    def fetchall(self):
        return [_Row(row) for row in self.cursor.fetchall()]


class PostgresConnection:
    def __init__(self, connection):
        self.connection = connection

    def execute(self, sql, params=None):
        import psycopg

        if sql.strip().upper() == "BEGIN IMMEDIATE":
            # Serialize quota reservations across workers in this database.
            try:
                self.connection.execute("SELECT pg_advisory_xact_lock(809138721)")
            except (psycopg.OperationalError, psycopg.InterfaceError):
                raise DatabaseUnavailableError("持久数据库暂时不可用。") from None
            return None
        sql = sql.replace(" IS ?", " IS NOT DISTINCT FROM %s").replace("?", "%s")
        try:
            return _Cursor(self.connection.execute(sql, params))
        except (psycopg.OperationalError, psycopg.InterfaceError):
            raise DatabaseUnavailableError("持久数据库暂时不可用。") from None

    def commit(self):
        import psycopg

        try:
            self.connection.commit()
        except (psycopg.OperationalError, psycopg.InterfaceError):
            raise DatabaseUnavailableError("持久数据库暂时不可用。") from None

    def rollback(self):
        import psycopg

        try:
            self.connection.rollback()
        except (psycopg.OperationalError, psycopg.InterfaceError):
            raise DatabaseUnavailableError("持久数据库暂时不可用。") from None

    def close(self):
        self.connection.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, _exc, _tb):
        try:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
        finally:
            self.close()


class DatabaseBackend:
    def __init__(
        self,
        *,
        database_path: str | Path | None = None,
        url: str | None = None,
        allow_insecure_local_test: bool = False,
        require_verified_tls: bool = False,
    ):
        if bool(database_path) == bool(url):
            raise DatabaseConfigurationError("必须且只能配置一个数据库连接目标。")
        self.path = Path(database_path) if database_path else None
        self.url = url
        self.sslmode = None
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
        else:
            parsed = urlsplit(url)
            modes = parse_qs(parsed.query).get("sslmode", [])
            mode = modes[0] if len(modes) == 1 else ""
            local_test = (
                allow_insecure_local_test
                and not require_verified_tls
                and parsed.hostname in {"localhost", "127.0.0.1", "::1"}
                and mode == "disable"
            )
            allowed_modes = (
                {"verify-full"}
                if require_verified_tls
                else {"require", "verify-ca", "verify-full"}
            )
            if parsed.scheme not in {"postgresql", "postgres"} or not (
                local_test or mode in allowed_modes
            ):
                raise DatabaseConfigurationError(
                    "生产 DATABASE_URL 必须为符合 TLS 策略的 PostgreSQL URL。"
                )
            self.sslmode = mode

    def connect(self):
        if self.path:
            connection = sqlite3.connect(self.path, timeout=10)
            connection.row_factory = sqlite3.Row
            connection.execute("PRAGMA foreign_keys = ON")
            return connection
        import psycopg
        from psycopg.rows import dict_row

        try:
            return PostgresConnection(
                psycopg.connect(
                    self.url,
                    row_factory=dict_row,
                    connect_timeout=8,
                    sslmode=self.sslmode,
                )
            )
        except psycopg.OperationalError:
            raise DatabaseUnavailableError("持久数据库暂时不可用。") from None
