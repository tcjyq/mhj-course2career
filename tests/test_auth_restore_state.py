"""A new WebSocket must wait for browser storage hydration before Guest."""

from pathlib import Path

from streamlit.testing.v1 import AppTest

from course2career.auth_service import AuthService
from course2career.permissions import Role
from course2career.product_repository import SQLiteProductRepository
from course2career.ui import browser_auth

APP_PATH = Path(__file__).resolve().parents[1] / "app.py"


def _new_app(monkeypatch, tmp_path, phases):
    monkeypatch.setenv("COURSE2CAREER_DATABASE_PATH", str(tmp_path / "restore.db"))
    values = iter(phases)
    monkeypatch.setattr(
        browser_auth, "read_browser_storage", lambda **_kwargs: next(values)
    )
    return AppTest.from_file(APP_PATH)


def test_pending_then_token_restores_in_next_run(monkeypatch, tmp_path):
    repo = SQLiteProductRepository(tmp_path / "restore.db")
    auth = AuthService(repo)
    user = auth.register("pending_user", "synthetic-password-123")
    token = auth.create_session(user)
    app = _new_app(
        monkeypatch,
        tmp_path,
        [
            browser_auth.BrowserStorageState("PENDING"),
            browser_auth.BrowserStorageState("TOKEN_PRESENT", token),
        ],
    )

    app.run()
    assert not app.exception
    assert any("正在全力加载…" in item.value for item in app.info)
    assert "principal" not in app.session_state

    app.run()
    assert not app.exception
    assert app.session_state.principal.user_id == user.user_id
    assert app.session_state.principal.role == Role.USER


def test_pending_then_no_token_becomes_guest(monkeypatch, tmp_path):
    app = _new_app(
        monkeypatch,
        tmp_path,
        [
            browser_auth.BrowserStorageState("PENDING"),
            browser_auth.BrowserStorageState("NO_TOKEN"),
        ],
    )
    app.run()
    assert not app.exception
    assert "principal" not in app.session_state
    app.run()
    assert not app.exception
    assert app.session_state.principal.role == Role.GUEST


def test_invalid_token_becomes_guest_and_schedules_cleanup(monkeypatch, tmp_path):
    app = _new_app(
        monkeypatch,
        tmp_path,
        [browser_auth.BrowserStorageState("TOKEN_PRESENT", "A" * 43)],
    )
    app.run()
    assert not app.exception
    assert app.session_state.principal.role == Role.GUEST
    assert app.session_state.pending_auth_storage["action"] == "clear"


def test_login_waits_for_browser_write_before_showing_authenticated_ui(
    monkeypatch, tmp_path
):
    repo = SQLiteProductRepository(tmp_path / "restore.db")
    auth = AuthService(repo)
    user = auth.register("write_pending_user", "synthetic-password-123")
    token = auth.create_session(user)
    app = _new_app(
        monkeypatch,
        tmp_path,
        [
            browser_auth.BrowserStorageState("PENDING"),
            browser_auth.BrowserStorageState("TOKEN_PRESENT", token),
        ],
    )
    app.session_state.principal = user
    app.session_state.pending_auth_storage = {
        "action": "set",
        "nonce": "write-confirmation",
        "token": token,
    }

    app.run()
    assert not app.exception
    assert any("正在全力加载…" in item.value for item in app.info)
    assert len(app.sidebar.button) == 0

    app.run()
    assert not app.exception
    assert "pending_auth_storage" not in app.session_state
    assert app.session_state.principal.user_id == user.user_id
