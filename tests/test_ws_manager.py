"""
Unit tests: websocket.manager

ConnectionManager 是純 in-memory + asyncio,不需要任何外部依賴。
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.websocket.manager import Connection, ConnectionManager


def _mock_ws() -> MagicMock:
    ws = MagicMock()
    ws.send_json = AsyncMock()
    return ws


def _make_conn(user_id: int = 1, username: str = "alice", permissions: set | None = None) -> Connection:
    return Connection(
        ws=_mock_ws(),
        user_id=user_id,
        username=username,
        permissions=permissions or {"dashboard:view"},
    )


# ── connect / disconnect ──────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_connect_increases_count():
    mgr = ConnectionManager()
    ws = _mock_ws()
    await mgr.connect(ws, user_id=1, username="alice", permissions={"dashboard:view"})
    assert mgr.total_connections == 1
    assert mgr.total_users == 1


@pytest.mark.asyncio
async def test_disconnect_removes_conn():
    mgr = ConnectionManager()
    ws = _mock_ws()
    conn = await mgr.connect(ws, user_id=1, username="alice", permissions=set())
    await mgr.disconnect(conn)
    assert mgr.total_connections == 0
    assert mgr.total_users == 0


@pytest.mark.asyncio
async def test_same_user_multiple_connections():
    mgr = ConnectionManager()
    conn1 = await mgr.connect(_mock_ws(), user_id=1, username="alice", permissions=set())
    conn2 = await mgr.connect(_mock_ws(), user_id=1, username="alice", permissions=set())
    assert mgr.total_connections == 2
    assert mgr.total_users == 1   # 同一個 user
    await mgr.disconnect(conn1)
    assert mgr.total_users == 1   # conn2 還在
    await mgr.disconnect(conn2)
    assert mgr.total_users == 0


# ── join / leave room ─────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_join_and_leave_room():
    mgr = ConnectionManager()
    conn = await mgr.connect(_mock_ws(), user_id=1, username="alice", permissions=set())
    await mgr.join_room(conn, "task:abc")
    assert "task:abc" in mgr.rooms_snapshot()
    assert mgr.rooms_snapshot()["task:abc"] == 1

    await mgr.leave_room(conn, "task:abc")
    assert "task:abc" not in mgr.rooms_snapshot()


# ── broadcast_room ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_broadcast_room_permission_filter():
    mgr = ConnectionManager()
    conn_admin = await mgr.connect(
        _mock_ws(), user_id=1, username="admin", permissions={"audit:view"}
    )
    conn_user = await mgr.connect(
        _mock_ws(), user_id=2, username="bob", permissions={"dashboard:view"}
    )
    await mgr.join_room(conn_admin, "admin:tasks")
    await mgr.join_room(conn_user, "admin:tasks")

    sent = await mgr.broadcast_room(
        "admin:tasks",
        {"type": "task_event"},
        required_permission="audit:view",
    )
    assert sent == 1  # 只有 admin 拿到
    conn_admin.ws.send_json.assert_called_once()
    conn_user.ws.send_json.assert_not_called()


@pytest.mark.asyncio
async def test_send_to_failed_disconnects():
    """send_to 失敗時應靜默斷線,不拋例外。"""
    mgr = ConnectionManager()
    ws = _mock_ws()
    ws.send_json = AsyncMock(side_effect=RuntimeError("broken pipe"))
    conn = await mgr.connect(ws, user_id=1, username="alice", permissions=set())
    result = await mgr.send_to(conn, {"type": "test"})
    assert result is False
    assert mgr.total_connections == 0  # 應該已被清除


# ── rooms_snapshot 不應洩漏空 room ────────────────────────────────────────

@pytest.mark.asyncio
async def test_empty_room_cleaned_up():
    mgr = ConnectionManager()
    conn = await mgr.connect(_mock_ws(), user_id=1, username="alice", permissions=set())
    await mgr.join_room(conn, "task:xyz")
    await mgr.disconnect(conn)  # disconnect 應把 room 清掉
    assert "task:xyz" not in mgr.rooms_snapshot()
