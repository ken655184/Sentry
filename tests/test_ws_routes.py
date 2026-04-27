"""
Unit tests: websocket.routes  ── _validate_room

純邏輯測試,不需要起 FastAPI server。
"""

from __future__ import annotations

from app.websocket.manager import Connection
from app.websocket.routes import _validate_room
from unittest.mock import MagicMock


def _conn(permissions: set[str]) -> Connection:
    return Connection(
        ws=MagicMock(),
        user_id=1,
        username="tester",
        permissions=permissions,
    )


def test_valid_task_room():
    assert _validate_room("task:abc-123-def", _conn(set())) is None


def test_valid_admin_room_with_permission():
    assert _validate_room("admin:tasks", _conn({"audit:view"})) is None


def test_admin_room_without_permission():
    err = _validate_room("admin:tasks", _conn({"dashboard:view"}))
    assert err is not None
    assert "forbidden" in err


def test_unknown_prefix_rejected():
    err = _validate_room("internal:secret", _conn({"audit:view"}))
    assert err is not None


def test_empty_room_rejected():
    err = _validate_room("", _conn(set()))
    assert err is not None


def test_room_too_long():
    err = _validate_room("task:" + "x" * 300, _conn(set()))
    assert err is not None
    assert "long" in err


def test_non_string_room():
    # 雖然 API 層有 pydantic,這個函式本身也要能處理
    err = _validate_room(None, _conn(set()))  # type: ignore[arg-type]
    assert err is not None
