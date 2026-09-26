"""Guard the destructive half of the synthetic remote restore drill."""

import pytest

from scripts import verify_remote_persistence as drill


class FakeConnection:
    def __init__(self, tables, counts, synthetic_users):
        self.tables = tables
        self.counts = counts
        self.synthetic_users = synthetic_users

    def connect(self):
        return self

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        pass

    def execute(self, query, _parameters=None):
        if "FROM pg_catalog.pg_tables" in query:
            return FakeResult(rows=self.tables)
        if "WHERE username" in query:
            return FakeResult(value=self.synthetic_users)
        table = query.rsplit(".", 1)[-1]
        return FakeResult(value=self.counts[table])


class FakeResult:
    def __init__(self, rows=None, value=None):
        self.rows = rows
        self.value = value

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return (self.value,)


@pytest.fixture
def expected_counts():
    return {table: 0 for table in drill.TABLES} | {
        "users": 1,
        "api_usage": 1,
        "analysis_records": 1,
        "user_api_keys": 1,
        "user_provider_profiles": 1,
        "user_byok_settings": 1,
        "schema_migrations": 2,
    }


def test_restore_accepts_empty_target(monkeypatch, expected_counts):
    monkeypatch.setattr(
        drill,
        "DatabaseBackend",
        lambda **_kwargs: FakeConnection([], {}, 0),
    )
    drill._safe_restore_target("synthetic", expected_counts)


def test_restore_accepts_only_complete_synthetic_target(monkeypatch, expected_counts):
    tables = [{"schemaname": "public", "tablename": table} for table in drill.TABLES]
    monkeypatch.setattr(
        drill,
        "DatabaseBackend",
        lambda **_kwargs: FakeConnection(tables, expected_counts, 1),
    )
    drill._safe_restore_target("synthetic", expected_counts)


@pytest.mark.parametrize("change", ["other_table", "other_user", "other_data"])
def test_restore_refuses_unexpected_target(monkeypatch, expected_counts, change):
    tables = [{"schemaname": "public", "tablename": table} for table in drill.TABLES]
    counts = dict(expected_counts)
    synthetic_users = 1
    if change == "other_table":
        tables.append({"schemaname": "public", "tablename": "private_data"})
    elif change == "other_user":
        synthetic_users = 0
    else:
        counts["users"] = 2
    monkeypatch.setattr(
        drill,
        "DatabaseBackend",
        lambda **_kwargs: FakeConnection(tables, counts, synthetic_users),
    )
    with pytest.raises(RuntimeError, match="refusing cleanup"):
        drill._safe_restore_target("synthetic", expected_counts)
