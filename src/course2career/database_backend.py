"""Small DB boundary shared by the existing repository SQL on SQLite and PostgreSQL."""

import logging
import re
import sqlite3
import weakref
from pathlib import Path
from threading import Lock
from urllib.parse import parse_qs, urlsplit


class DatabaseConfigurationError(ValueError):
    """A production database setting cannot safely provide durable storage."""


class DatabaseUnavailableError(RuntimeError):
    """The persistent database cannot be reached; details are deliberately hidden."""

    def __init__(
        self,
        message: str,
        *,
        failure_category: str = "UNKNOWN",
        source_type: str = "DatabaseUnavailableError",
    ) -> None:
        super().__init__(message)
        self.failure_category = failure_category
        self.source_type = source_type


_SAFE_EXCEPTION_TYPES = {
    "DatabaseConfigurationError",
    "DatabaseUnavailableError",
    "OperationalError",
    "InterfaceError",
    "ProgrammingError",
    "InsufficientPrivilege",
    "InvalidCatalogName",
    "RuntimeError",
    "OSError",
}
_FAILURE_CATEGORIES = {
    "CONFIGURATION",
    "TLS_CERTIFICATE",
    "TLS_HOSTNAME",
    "DNS",
    "NETWORK",
    "AUTHENTICATION",
    "DATABASE_NOT_FOUND",
    "PERMISSION",
    "MIGRATION",
    "UNKNOWN",
}


def _safe_exception_type(exc: Exception) -> str:
    name = getattr(exc, "source_type", type(exc).__name__)
    return name if name in _SAFE_EXCEPTION_TYPES else "Exception"


def _redacted_error_text(exc: Exception) -> str:
    """Redact connection details before classifying an exception message."""
    message = str(exc)
    message = re.sub(r"(?i)postgres(?:ql)?(?:\\)?://\S+", "[REDACTED_URL]", message)
    message = re.sub(
        r"(?i)\b(?:password|passwd|pwd|user|username|database_url|token|api[_-]?key)"
        r"\s*[:=]\s*(?:\"[^\"]*\"|'[^']*'|\S+)",
        "[REDACTED_CREDENTIAL]",
        message,
    )
    message = re.sub(
        r"(?i)\b(?:napi|sk|ds)[_-][A-Za-z0-9_-]{12,}\b",
        "[REDACTED_CREDENTIAL]",
        message,
    )
    return re.sub(r"\b[A-Za-z0-9+/_=-]{24,}\b", "[REDACTED_CREDENTIAL]", message)


def classify_database_failure(exc: Exception) -> str:
    """Return a fixed diagnostic category; never return exception text."""
    if isinstance(exc, DatabaseConfigurationError):
        return "CONFIGURATION"
    if (
        isinstance(exc, DatabaseUnavailableError)
        and isinstance(exc.failure_category, str)
        and exc.failure_category in _FAILURE_CATEGORIES
        and exc.failure_category != "UNKNOWN"
    ):
        return exc.failure_category
    sqlstate = getattr(exc, "sqlstate", None)
    if sqlstate in {"28P01", "28000"}:
        return "AUTHENTICATION"
    if sqlstate == "3D000":
        return "DATABASE_NOT_FOUND"
    if sqlstate == "42501":
        return "PERMISSION"
    if sqlstate in {"42P01", "42P07", "42703"}:
        return "MIGRATION"
    if isinstance(sqlstate, str) and sqlstate.startswith("08"):
        return "NETWORK"
    message = _redacted_error_text(exc).lower()
    if any(
        term in message
        for term in (
            "hostname mismatch",
            "host name mismatch",
            "does not match the host",
            "does not match host name",
            "hostname verification failed",
        )
    ):
        return "TLS_HOSTNAME"
    if any(
        term in message
        for term in ("certificate", "sslrootcert", "tls handshake", "ssl error")
    ):
        return "TLS_CERTIFICATE"
    if any(
        term in message
        for term in (
            "could not translate host name",
            "name or service not known",
            "getaddrinfo",
            "nodename nor servname",
        )
    ):
        return "DNS"
    if any(
        term in message
        for term in (
            "password authentication failed",
            "authentication failed",
            "no pg_hba.conf entry",
        )
    ):
        return "AUTHENTICATION"
    if "database" in message and "does not exist" in message:
        return "DATABASE_NOT_FOUND"
    if any(
        term in message
        for term in ("permission denied", "insufficient privilege", "must be owner")
    ):
        return "PERMISSION"
    if any(
        term in message for term in ("schema", "migration", "relation does not exist")
    ):
        return "MIGRATION"
    if any(
        term in message
        for term in (
            "connection refused",
            "connection timed out",
            "timeout expired",
            "network is unreachable",
            "could not connect",
        )
    ):
        return "NETWORK"
    return "UNKNOWN"


def log_database_startup_failure(exc: Exception) -> None:
    logging.getLogger(__name__).error(
        "database_startup_failure exception_type=%s failure_category=%s",
        _safe_exception_type(exc),
        classify_database_failure(exc),
    )


def _unavailable(exc: Exception) -> DatabaseUnavailableError:
    return DatabaseUnavailableError(
        "持久数据库暂时不可用。",
        failure_category=classify_database_failure(exc),
        source_type=_safe_exception_type(exc),
    )


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
    def __init__(self, connection, *, release=None):
        self.connection = connection
        self._release = release
        self._closed = False

    def execute(self, sql, params=None):
        import psycopg

        if sql.strip().upper() == "BEGIN IMMEDIATE":
            # Serialize quota reservations across workers in this database.
            try:
                self.connection.execute("SELECT pg_advisory_xact_lock(809138721)")
            except (psycopg.OperationalError, psycopg.InterfaceError) as exc:
                raise _unavailable(exc) from None
            return None
        sql = sql.replace(" IS ?", " IS NOT DISTINCT FROM %s").replace("?", "%s")
        try:
            return _Cursor(self.connection.execute(sql, params))
        except (psycopg.OperationalError, psycopg.InterfaceError) as exc:
            raise _unavailable(exc) from None

    def commit(self):
        import psycopg

        try:
            self.connection.commit()
        except (psycopg.OperationalError, psycopg.InterfaceError) as exc:
            raise _unavailable(exc) from None

    def rollback(self):
        import psycopg

        try:
            self.connection.rollback()
        except (psycopg.OperationalError, psycopg.InterfaceError) as exc:
            raise _unavailable(exc) from None

    def close(self):
        if not self._closed:
            self._closed = True
            if self._release is None:
                self.connection.close()
            else:
                self._release(self.connection)

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
        pool_max_size: int = 4,
        pool_timeout: float = 8,
    ):
        if bool(database_path) == bool(url):
            raise DatabaseConfigurationError("必须且只能配置一个数据库连接目标。")
        self.path = Path(database_path) if database_path else None
        self.url = url
        self.sslmode = None
        self.require_verified_tls = require_verified_tls
        if not 1 <= pool_max_size <= 16 or pool_timeout <= 0:
            raise DatabaseConfigurationError("数据库连接池配置无效。")
        self._pool_max_size = pool_max_size
        self._pool_timeout = pool_timeout
        self._pool = None
        self._pool_lock = Lock()
        self._pool_finalizer = None
        self._closed = False
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
        from psycopg_pool import PoolClosed, PoolTimeout, TooManyRequests

        try:
            pool = self._get_pool()
            return PostgresConnection(pool.getconn(), release=pool.putconn)
        except (psycopg.OperationalError, psycopg.InterfaceError) as exc:
            raise _unavailable(exc) from None
        except (PoolClosed, PoolTimeout, TooManyRequests):
            raise DatabaseUnavailableError(
                "持久数据库暂时不可用。", failure_category="NETWORK"
            ) from None

    def _get_pool(self):
        from psycopg.rows import dict_row
        from psycopg_pool import ConnectionPool

        with self._pool_lock:
            if self._closed:
                raise DatabaseUnavailableError("持久数据库暂时不可用。")
            if self._pool is not None:
                return self._pool
            tls_options = {"sslmode": self.sslmode}
            if self.require_verified_tls:
                import certifi

                tls_options = {
                    "sslmode": "verify-full",
                    "sslrootcert": certifi.where(),
                }
            logger = logging.getLogger("psycopg.pool")
            if not any(isinstance(f, _SafePoolLogs) for f in logger.filters):
                logger.addFilter(_SafePoolLogs())
            pool = ConnectionPool(
                conninfo=self.url,
                kwargs={
                    "row_factory": dict_row,
                    "connect_timeout": 8,
                    **tls_options,
                },
                min_size=0,
                max_size=self._pool_max_size,
                max_waiting=16,
                timeout=self._pool_timeout,
                max_idle=60,
                max_lifetime=1800,
                reconnect_timeout=8,
                num_workers=2,
                check=ConnectionPool.check_connection,
                name="course2career",
                open=False,
            )
            pool.open()
            self._pool = pool
            # GC/cache replacement and normal process exit both release workers.
            self._pool_finalizer = weakref.finalize(self, pool.close)
            return pool

    def close(self) -> None:
        with self._pool_lock:
            self._closed = True
            if self._pool_finalizer is not None:
                self._pool_finalizer()


class _SafePoolLogs(logging.Filter):
    """Pool worker errors may contain DSNs: retain severity, suppress raw details."""

    def filter(self, record: logging.LogRecord) -> bool:
        record.msg = "postgres_pool_event level=%s"
        record.args = (record.levelname,)
        record.exc_info = None
        record.exc_text = None
        record.stack_info = None
        return True
