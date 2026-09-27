"""The frontend must explicitly distinguish hydration from an empty store."""

from course2career.ui.browser_auth import (
    BrowserStorageState,
    log_restore_state,
    parse_storage_state,
)


def test_async_initial_default_remains_pending():
    assert parse_storage_state(None, nonce="current") == BrowserStorageState("PENDING")
    assert parse_storage_state({}, nonce="current") == BrowserStorageState("PENDING")
    assert parse_storage_state(
        {"ready": True, "token": "A" * 43, "nonce": "previous", "ok": True},
        nonce="current",
    ) == BrowserStorageState("PENDING")


def test_ready_token_and_no_token_are_distinct():
    token = "A" * 43
    assert parse_storage_state(
        {"ready": True, "token": token, "nonce": "current", "ok": True},
        nonce="current",
    ) == BrowserStorageState("TOKEN_PRESENT", token)
    assert parse_storage_state(
        {"ready": True, "token": None, "nonce": "current", "ok": True},
        nonce="current",
    ) == BrowserStorageState("NO_TOKEN")


def test_storage_failure_reports_no_token_without_exposing_value():
    assert parse_storage_state(
        {"ready": True, "token": None, "nonce": "current", "ok": False},
        nonce="current",
    ) == BrowserStorageState("NO_TOKEN", ok=False)


def test_restore_diagnostics_never_log_browser_token_or_hash(caplog):
    token = "synthetic-opaque-token-" + "A" * 43
    state = BrowserStorageState("TOKEN_PRESENT", token)

    log_restore_state(state, server_session_found=True, restore_result="authenticated")

    assert "auth_restore_start" in caplog.text
    assert "storage_token_present=True" in caplog.text
    assert token not in caplog.text
    assert "token_hash" not in caplog.text
