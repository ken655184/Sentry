"""
Redis Pub/Sub → WebSocket manager 橋接。

FastAPI 啟動時(lifespan)開一個 asyncio background task,訂閱:
    task:*           所有 task_id 的進度事件 (psubscribe pattern)
    tasks:broadcast  管理員全域 task 面板
    system:events    系統事件 (heartbeat…)

收到訊息 → 解析 → 透過 ConnectionManager 推到對應的 WS room。

為什麼要這層?
- Celery worker 不在同一個 process / machine,直接推 WS 不可行
- 把「事件產生」(worker) 與「事件推送」(FastAPI) 完全解耦
- scale out 時 FastAPI 可以多開幾台,每台都訂閱同一個 Redis channel,
  每台自己負責推自己持有的那些 WS 連線 —— 不需要額外協調

Room 命名對應(跟 workers/progress.py channel 命名一致):
    Redis channel       → WS room
    task:{id}           → task:{id}       (使用者訂閱自己跑的 task)
    tasks:broadcast     → admin:tasks     (管理員總覽面板;需 audit:view 權限)
    system:events       → admin:system    (系統事件;同上)
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

import redis.asyncio as aioredis

from app.config import settings
from app.core.logging import get_logger
from app.websocket.manager import manager

logger = get_logger(__name__)

TASK_PATTERN = "task:*"
BROADCAST_CHANNEL = "tasks:broadcast"
SYSTEM_CHANNEL = "system:events"


class PubSubBridge:
    """
    生命週期:
        await bridge.start()   # app lifespan 啟動時
        await bridge.stop()    # app lifespan 關閉時
    """

    def __init__(self) -> None:
        self._redis: aioredis.Redis | None = None
        self._pubsub: aioredis.client.PubSub | None = None
        self._task: asyncio.Task | None = None
        self._stopping = asyncio.Event()

    async def start(self) -> None:
        if self._task and not self._task.done():
            return
        self._stopping.clear()
        self._redis = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )
        self._pubsub = self._redis.pubsub()
        await self._pubsub.psubscribe(TASK_PATTERN)
        await self._pubsub.subscribe(BROADCAST_CHANNEL, SYSTEM_CHANNEL)
        self._task = asyncio.create_task(self._run(), name="ws-pubsub-bridge")
        logger.info("pubsub_bridge.started")

    async def stop(self) -> None:
        self._stopping.set()
        if self._pubsub:
            try:
                await self._pubsub.punsubscribe()
                await self._pubsub.unsubscribe()
                await self._pubsub.aclose()
            except Exception:  # noqa: BLE001
                logger.exception("pubsub_bridge.stop_error")
        if self._task:
            try:
                await asyncio.wait_for(self._task, timeout=2.0)
            except (asyncio.TimeoutError, asyncio.CancelledError):
                self._task.cancel()
        if self._redis:
            await self._redis.aclose()
        logger.info("pubsub_bridge.stopped")

    async def _run(self) -> None:
        assert self._pubsub is not None
        # get_message + timeout 輪詢,而非 listen() 永久 block,讓 stop() 能乾淨退出
        while not self._stopping.is_set():
            try:
                msg = await self._pubsub.get_message(
                    ignore_subscribe_messages=True,
                    timeout=1.0,
                )
                if msg is None:
                    continue
                await self._dispatch(msg)
            except asyncio.CancelledError:
                break
            except Exception:  # noqa: BLE001
                # 單則訊息 dispatch 失敗不讓整個 bridge 倒
                logger.exception("pubsub_bridge.dispatch_error")

    async def _dispatch(self, msg: dict[str, Any]) -> None:
        channel: str = msg.get("channel") or msg.get("pattern") or ""
        raw = msg.get("data", "")
        try:
            data: dict = json.loads(raw)
        except (ValueError, TypeError):
            logger.warning("pubsub_bridge.bad_json", extra={"channel": channel})
            return

        if channel.startswith("task:"):
            # 個別 task 房間 —— 房間名稱與 Redis channel 相同
            room = channel
            await manager.broadcast_room(
                room,
                {"type": "task_event", **data},
            )

        elif channel == BROADCAST_CHANNEL:
            # 管理員的全域 task 面板:要有 audit:view 才看得到
            await manager.broadcast_room(
                "admin:tasks",
                {"type": "task_event", **data},
                required_permission="audit:view",
            )

        elif channel == SYSTEM_CHANNEL:
            # 系統事件(heartbeat…):要有 system:config 才能看
            await manager.broadcast_room(
                "admin:system",
                {"type": "system_event", **data},
                required_permission="system:config",
            )


# 模組單例 —— lifespan 會用這個
bridge = PubSubBridge()
