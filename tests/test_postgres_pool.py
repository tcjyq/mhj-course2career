"""Real synthetic PostgreSQL: reuse must not reuse a transaction or broken socket."""

import logging
import os
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlsplit

import pytest
from psycopg.pq import TransactionStatus

from course2career.database_backend import (
    DatabaseBackend,
    DatabaseConfigurationError,
    DatabaseUnavailableError,
    _SafePoolLogs,
)


@pytest.fixture
def backend():
    url = os.getenv("C08_TEST_DATABASE_URL")
    if not url:
        pytest.skip("Needs isolated C08_TEST_DATABASE_URL")
    if urlsplit(url).hostname not in {"localhost", "127.0.0.1", "::1"}:
        pytest.skip("Pool failure tests only run on a synthetic local target")
    backend = DatabaseBackend(
        url=url, allow_insecure_local_test=True, pool_max_size=1, pool_timeout=0.5
    )
    try:
        yield backend
    finally:
        backend.close()


@pytest.mark.postgres
def test_reuses_physical_connection_with_idle_transaction(backend):
    pids = []
    for _ in range(3):
        with backend.connect() as connection:
            assert (
                connection.connection.info.transaction_status == TransactionStatus.IDLE
            )
            pids.append(connection.execute("SELECT pg_backend_pid()").fetchone()[0])
    assert len(set(pids)) == 1
    assert backend._pool.get_stats()["connections_num"] == 1


@pytest.mark.postgres
@pytest.mark.parametrize("context_exit", [True, False])
def test_failed_or_uncommitted_work_is_rolled_back(backend, context_exit):
    with backend.connect() as connection:
        connection.execute("CREATE TEMP TABLE pool_rollback(value INTEGER)")
    if context_exit:
        with pytest.raises(RuntimeError), backend.connect() as connection:
            connection.execute("INSERT INTO pool_rollback VALUES (1)")
            raise RuntimeError("synthetic failure")
    else:
        connection = backend.connect()
        connection.execute("INSERT INTO pool_rollback VALUES (1)")
        connection.close()  # pool must reset before serving another request
    with backend.connect() as connection:
        assert connection.connection.info.transaction_status == TransactionStatus.IDLE
        assert (
            connection.execute("SELECT COUNT(*) FROM pool_rollback").fetchone()[0] == 0
        )


@pytest.mark.postgres
@pytest.mark.parametrize("idle", [True, False])
def test_closed_socket_is_discarded_and_replaced(backend, idle):
    connection = backend.connect()
    old_pid = connection.connection.info.backend_pid
    if idle:
        connection.close()
    connection.connection.close()
    if not idle:
        connection.close()
    with backend.connect() as healthy:
        assert healthy.connection.info.backend_pid != old_pid
        assert healthy.execute("SELECT 1").fetchone()[0] == 1


@pytest.mark.postgres
def test_exhaustion_has_bounded_wait_and_recovers(backend):
    held = backend.connect()
    try:
        with pytest.raises(DatabaseUnavailableError):
            backend.connect()
        assert backend._pool.get_stats()["pool_size"] == 1
    finally:
        held.close()
    with backend.connect() as connection:
        assert connection.execute("SELECT 1").fetchone()[0] == 1


@pytest.mark.postgres
def test_threads_get_exclusive_transactions(backend):
    def query(value):
        with backend.connect() as connection:
            assert (
                connection.connection.info.transaction_status == TransactionStatus.IDLE
            )
            return connection.execute("SELECT ? AS value", (value,)).fetchone()[0]

    with ThreadPoolExecutor(max_workers=4) as executor:
        assert list(executor.map(query, range(8))) == list(range(8))
    assert backend._pool.get_stats()["pool_size"] <= 1


@pytest.mark.postgres
def test_close_prevents_reopening_resource(backend):
    with backend.connect():
        pass
    backend.close()
    with pytest.raises(DatabaseUnavailableError):
        backend.connect()


def test_database_unavailable_is_fail_closed(tmp_path):
    backend = DatabaseBackend(
        url="postgresql://127.0.0.1:1/synthetic?sslmode=disable",
        allow_insecure_local_test=True,
        pool_timeout=0.15,
    )
    try:
        with pytest.raises(DatabaseUnavailableError):
            backend.connect()
        assert not list(tmp_path.iterdir())
    finally:
        backend.close()


@pytest.mark.parametrize("size,timeout", [(0, 8), (17, 8), (4, 0)])
def test_pool_settings_are_bounded(size, timeout):
    with pytest.raises(DatabaseConfigurationError):
        DatabaseBackend(
            url="postgresql://localhost/synthetic?sslmode=verify-full",
            pool_max_size=size,
            pool_timeout=timeout,
        )


def test_pool_worker_logs_do_not_expose_connection_details(caplog):
    logger = logging.getLogger("psycopg.pool")
    guard = _SafePoolLogs()
    logger.addFilter(guard)
    try:
        with caplog.at_level(logging.WARNING):
            logger.warning("connection error: %s", "synthetic-private-DSN")
        assert "synthetic-private-DSN" not in caplog.text
        assert "postgres_pool_event level=WARNING" in caplog.text
    finally:
        logger.removeFilter(guard)
