"""
WebSocket 連線管理。

職責:
- 維護「user_id → 多條連線」的 map(同一人可能開多個分頁)
- 維護「room → 多條連線」的 map(task 房間、管理員面板…)
- 廣播 / 精準推送
- 連線斷開清理

設計重點:
- 全部是 in-process 的 in-memory state —— 每個 FastAPI process 一份
- 跨 process / 跨 instance 的廣播由 Redis Pub/Sub 負責,WS manager 只管
  「這個 process 裡有哪些 WS 連線」,不管別的 instance
- asyncio.Lock 保護三個集合的一致性;實際上 FastAPI 的 async handler 在
  同一個 event loop 裡跑,Lock 主要防的是 disconnect 和 broadcast 同時進來
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket

from app.core.logging import get_logger

logger = get_logger(__name__)


@dataclass
class Connection:
    """一條 WebSocket 連線的 metadata。"""

    ws: WebSocket
    user_id: int
    username: str
    permissions: set[str]           # 從 JWT payload 展開的 permission set
    rooms: set[str] = field(default_factory=set)


class ConnectionManager:

    def __init__(self) -> None:
        self._by_user: dict[int, set[Connection]] = defaultdict(set)
        self._by_room: dict[str, set[Connection]] = defaultdict(set)
        self._all: set[Connection] = set()
        self._lock = asyncio.Lock()

    # ------------------------------------------------------------------ #
    #  連線管理                                                             #
    # ------------------------------------------------------------------ #

    async def connect(
        self,
        ws: WebSocket,
        user_id: int,
        username: str,
        permissions: set[str],
    ) -> Connection:
        """建立連線並加入管理(WebSocket 必須已經 accept)。"""
        conn = Connection(
            ws=ws,
            user_id=user_id,
            username=username,
            permissions=permissions,
        )
        async with self._lock:
            self._by_user[user_id].add(conn)
            self._all.add(conn)
        logger.info(
            "ws.connect",
            extra={"user_id": user_id, "username": username, "total": len(self._all)},
        )
        return conn

    async def disconnect(self, conn: Connection) -> None:
        async with self._lock:
            self._all.discard(conn)
            self._by_user[conn.user_id].discard(conn)
            if not self._by_user[conn.user_id]:
                del self._by_user[conn.user_id]
            for room in list(conn.rooms):
                self._by_room[room].discard(conn)
                if not self._by_room[room]:
                    del self._by_room[room]
            conn.rooms.clear()
        logger.info(
            "ws.disconnect",
            extra={"user_id": conn.user_id, "remaining": len(self._all)},
        )

    async def join_room(self, conn: Connection, room: str) -> None:
        async with self._lock:
            self._by_room[room].add(conn)
            conn.rooms.add(room)

    async def leave_room(self, conn: Connection, room: str) -> None:
        async with self._lock:
            self._by_room[room].discard(conn)
            conn.rooms.discard(room)
            if not self._by_room.get(room):
                self._by_room.pop(room, None)

    # ------------------------------------------------------------------ #
    #  發送                                                                #
    # ------------------------------------------------------------------ #

    async def send_to(self, conn: Connection, message: Any) -> bool:
        """推給單一連線。失敗時靜默斷線,回傳是否成功。"""
        try:
            await conn.ws.send_json(message)
            return True
        except Exception:  # noqa: BLE001
            logger.debug("ws.send_failed", extra={"user_id": conn.user_id})
            await self.disconnect(conn)
            return False

    async def send_to_user(self, user_id: int, message: Any) -> int:
        """推給某使用者的所有連線。回傳送達條數。"""
        targets = list(self._by_user.get(user_id, set()))
        sent = 0
        for conn in targets:
            if await self.send_to(conn, message):
                sent += 1
        return sent

    async def broadcast_room(
        self,
        room: str,
        message: Any,
        required_permission: str | None = None,
    ) -> int:
        """
        廣播到某個 room。
        required_permission:只推給具備指定 permission 的連線(例如 audit:view)。
        """
        targets = list(self._by_room.get(room, set()))
        sent = 0
        for conn in targets:
            if required_permission and required_permission not in conn.permissions:
                continue
            if await self.send_to(conn, message):
                sent += 1
        return sent

    async def broadcast_all(
        self,
        message: Any,
        required_permission: str | None = None,
    ) -> int:
        targets = list(self._all)
        sent = 0
        for conn in targets:
            if required_permission and required_permission not in conn.permissions:
                continue
            if await self.send_to(conn, message):
                sent += 1
        return sent

    # ------------------------------------------------------------------ #
    #  Metrics                                                             #
    # ------------------------------------------------------------------ #

    @property
    def total_connections(self) -> int:
        return len(self._all)

    @property
    def total_users(self) -> int:
        return len(self._by_user)

    def rooms_snapshot(self) -> dict[str, int]:
        return {room: len(conns) for room, conns in self._by_room.items()}


# 全域單例 —— ws endpoint 與 pubsub_bridge 都用這個
manager = ConnectionManager()
