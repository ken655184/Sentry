"""
WebSocket 路由。

main.py 已有:
    from app.websocket.routes import ws_router
    app.include_router(ws_router, prefix="/ws")

所以這個模組必須:
1. 檔案放在 app/websocket/routes.py
2. 匯出名稱為 ws_router
3. endpoint path 設為 "" 或 "/",因為前綴 /ws 由 main.py 的 include_router 給

最終 URL:  ws://host/ws?token=<jwt>

認證:
- 瀏覽器 WebSocket API 不允許自訂 header,所以 token 走 query string
- 用 Part 1 的 decode_token(app.core.security),欄位一致
- payload["sub"] 是 username(Part 1 的 create_access_token 用 username 當 sub)
- permissions 從 token payload["permissions"] 讀(若不存在則 [])

客戶端協議(JSON,每則訊息都帶 op):
    → client → server
        {"op": "subscribe",   "room": "task:<task_id>"}
        {"op": "subscribe",   "room": "admin:tasks"}
        {"op": "unsubscribe", "room": "task:<task_id>"}
        {"op": "ping"}

    ← server → client
        {"type": "welcome",     "user_id": ..., "username": ...}
        {"type": "ack",         "op": "subscribe",   "room": "..."}
        {"type": "ack",         "op": "unsubscribe",  "room": "..."}
        {"type": "error",       "message": "..."}
        {"type": "pong"}
        {"type": "task_event",  "task_id": "...", "event": "...", "payload": {...}}
        {"type": "system_event","event": "...", "payload": {...}}
"""

from __future__ import annotations

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from app.auth.permissions import Permission
from app.core.exceptions import AuthenticationError
from app.core.logging import get_logger
from app.core.security import decode_token
from app.websocket.manager import Connection, manager
from app.websocket.metrics import WS_CONNECTIONS_TOTAL, WS_ACTIVE_CONNECTIONS

logger = get_logger(__name__)

ws_router = APIRouter()

# 每條連線最多加入幾個 room,避免惡意 / bug 導致 manager 佔記憶體
MAX_ROOMS_PER_CONN = 20

# 合法的 room 前綴白名單
ALLOWED_ROOM_PREFIXES = ("task:", "admin:")


@ws_router.websocket("")
async def websocket_endpoint(
    websocket: WebSocket,
    token: str = Query(..., description="JWT access token"),
):
    """
    /ws?token=<jwt>

    步驟:
        1. 驗 JWT(在 accept 之前,失敗就用 4008 關閉)
        2. accept + 加入 manager
        3. 送 welcome 訊息
        4. 進入 receive 迴圈,直到 client 斷線或例外
        5. finally 必定 disconnect
    """
    # ── 1. 驗 JWT ─────────────────────────────────────────────────────
    try:
        payload = decode_token(token)
    except AuthenticationError as exc:
        # 4008:policy violation;在 accept 之前呼叫 close 不需要 accept
        await websocket.close(code=4008, reason=str(exc))
        return

    if payload.get("type") != "access":
        await websocket.close(code=4008, reason="wrong token type")
        return

    username: str = payload.get("sub", "")
    # Part 1 的 create_access_token 把 user.id 存在 "uid"
    permissions: set[str] = set(payload.get("permissions", []))
    user_id: int = int(payload["uid"]) if "uid" in payload else abs(hash(username)) % 10**9

    # ── 2. Accept + 加入 manager ──────────────────────────────────────
    await websocket.accept()
    conn: Connection = await manager.connect(
        ws=websocket,
        user_id=user_id,
        username=username,
        permissions=permissions,
    )
    WS_CONNECTIONS_TOTAL.inc()
    WS_ACTIVE_CONNECTIONS.inc()

    # ── 3. Welcome ────────────────────────────────────────────────────
    await manager.send_to(conn, {
        "type": "welcome",
        "user_id": user_id,
        "username": username,
        "permissions": sorted(permissions),
    })

    # ── 4. Receive 迴圈 ───────────────────────────────────────────────
    try:
        while True:
            try:
                msg = await websocket.receive_json()
            except Exception:
                # 收不到訊息 = client 端已斷,退出迴圈
                break
            await _handle_op(conn, msg)
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        logger.exception("ws.unexpected_error", extra={"username": username})
    finally:
        WS_ACTIVE_CONNECTIONS.dec()
        await manager.disconnect(conn)


async def _handle_op(conn: Connection, msg: dict) -> None:
    """
    處理單一 client → server 訊息。
    不合法 → 回 error,不踢連線(避免前端 bug 導致意外斷線)。
    """
    op = msg.get("op")

    # ── ping ──────────────────────────────────────────────────────────
    if op == "ping":
        await manager.send_to(conn, {"type": "pong"})
        return

    # ── subscribe ─────────────────────────────────────────────────────
    if op == "subscribe":
        room = msg.get("room", "")
        err = _validate_room(room, conn)
        if err:
            await manager.send_to(conn, {"type": "error", "message": err})
            return
        if len(conn.rooms) >= MAX_ROOMS_PER_CONN:
            await manager.send_to(conn, {"type": "error", "message": "too many rooms"})
            return
        await manager.join_room(conn, room)
        await manager.send_to(conn, {"type": "ack", "op": "subscribe", "room": room})
        return

    # ── unsubscribe ───────────────────────────────────────────────────
    if op == "unsubscribe":
        room = msg.get("room", "")
        if not isinstance(room, str) or not room:
            await manager.send_to(conn, {"type": "error", "message": "invalid room"})
            return
        await manager.leave_room(conn, room)
        await manager.send_to(conn, {"type": "ack", "op": "unsubscribe", "room": room})
        return

    # ── unknown ───────────────────────────────────────────────────────
    await manager.send_to(conn, {"type": "error", "message": f"unknown op: {op!r}"})


def _validate_room(room: str, conn: Connection) -> str | None:
    """
    回傳錯誤訊息字串;None 表示合法。

    規則:
    - 必須是字串且不為空
    - 長度上限 200
    - 必須符合白名單前綴
    - admin:* 只有具備 audit:view 或 system:config 的人才能進
    """
    if not isinstance(room, str) or not room:
        return "invalid room"
    if len(room) > 200:
        return "room name too long"
    if not any(room.startswith(p) for p in ALLOWED_ROOM_PREFIXES):
        return f"room must start with one of: {ALLOWED_ROOM_PREFIXES}"
    if room.startswith("admin:"):
        allowed_admin_perms = {Permission.AUDIT_VIEW, Permission.SYSTEM_CONFIG}
        if not (conn.permissions & allowed_admin_perms):
            return "forbidden: missing admin permission"
    return None
