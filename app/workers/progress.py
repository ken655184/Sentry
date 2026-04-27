"""
Task 進度 / 事件廣播。

流程:
    Celery worker --publish--> Redis Pub/Sub --subscribe--> FastAPI WS bridge --> 前端

為什麼不讓 Celery 直接推到 WS?
- Worker process 跟 FastAPI process 是分開的,WS 連線只在 FastAPI 這邊
- 用 Redis Pub/Sub 橋接最簡單,FastAPI 那頭訂閱 pattern 就收得到所有事件
- 進度事件是 ephemeral 的,不該寫 DB,否則會把 audit_logs 淹掉

Channel 命名:
    task:{task_id}     單一 task 的事件(對應某個使用者開的 task 頁)
    tasks:broadcast    所有 task 的事件彙整(給管理員總覽用)
    system:events      系統事件(heartbeat、worker 上線…)

注意 Redis 的使用:
- 這個模組走 REDIS_URL (db 0),刻意跟 broker (db 1) / backend (db 2) 分開
- Celery worker 是 prefork 多 process;redis.Redis client 在 fork 之後才用,
  每個 worker process 會自然擁有自己的 connection pool,用 lazy singleton 即可
"""

from __future__ import annotations

import json
from typing import Any

import redis

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


_redis_client: redis.Redis | None = None


def _get_redis() -> redis.Redis:
    global _redis_client
    if _redis_client is None:
        _redis_client = redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_keepalive=True,
        )
    return _redis_client


def _channel_for_task(task_id: str) -> str:
    return f"task:{task_id}"


BROADCAST_CHANNEL = "tasks:broadcast"
SYSTEM_CHANNEL = "system:events"


def publish_task_event(task_id: str, event: str, payload: dict[str, Any] | None = None) -> None:
    """
    發佈一則 task 事件到兩個 channel:
        task:{task_id}     → 該 task 專屬訂閱者
        tasks:broadcast    → 管理員全域面板

    event 枚舉(前端好 switch):
        started | progress | finished | failed | log
    """
    message = {
        "task_id": task_id,
        "event": event,
        "payload": payload or {},
    }
    body = json.dumps(message, ensure_ascii=False, default=str)
    try:
        pipe = _get_redis().pipeline()
        pipe.publish(_channel_for_task(task_id), body)
        pipe.publish(BROADCAST_CHANNEL, body)
        pipe.execute()
    except redis.RedisError as exc:
        # 廣播失敗絕不能讓 task 本身失敗 — 只記錄
        logger.warning(
            "publish_task_event.redis_error",
            extra={"task_id": task_id, "err": str(exc)},
        )


def publish_system_event(event: str, payload: dict[str, Any] | None = None) -> None:
    """系統級事件(例:worker heartbeat、節點重啟)。"""
    body = json.dumps({"event": event, "payload": payload or {}}, ensure_ascii=False, default=str)
    try:
        _get_redis().publish(SYSTEM_CHANNEL, body)
    except redis.RedisError as exc:
        logger.warning("publish_system_event.redis_error", extra={"event": event, "err": str(exc)})


class ProgressReporter:
    """
    讓 task 程式碼以 OO 方式回報進度。

    用法:
        with ProgressReporter(task_id, total=len(items), label="掃描") as p:
            for i, item in enumerate(items, 1):
                do_work(item)
                p.update(i, note=item.name)

    設計說明:
    - 進度事件刻意不寫 Celery backend — backend 只存最後一個 retval,
      逐筆寫進度成本太高。走 Pub/Sub,純 in-memory,前端拿到即可拋棄。
    - update() 內建節流,只有百分比跳動才真的推訊息,避免 10 萬筆把 Redis 灌爆。
    """

    def __init__(self, task_id: str, total: int | None = None, label: str = "") -> None:
        self.task_id = task_id
        self.total = total
        self.label = label
        self._last_pct = -1

    def __enter__(self) -> "ProgressReporter":
        publish_task_event(
            self.task_id,
            "progress",
            {"current": 0, "total": self.total, "percent": 0, "label": self.label},
        )
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        # 收尾留給 task_postrun / task_failure signal 處理,避免重複發 finished
        return None

    def update(self, current: int, note: str = "") -> None:
        if self.total and self.total > 0:
            pct = int(current / self.total * 100)
        else:
            pct = -1

        # 節流:百分比沒動就不發;但 100% 一定要發(確保前端知道完成進度)
        if pct == self._last_pct and pct != 100:
            return
        self._last_pct = pct

        publish_task_event(
            self.task_id,
            "progress",
            {
                "current": current,
                "total": self.total,
                "percent": pct,
                "label": self.label,
                "note": note,
            },
        )

    def log(self, message: str, level: str = "info") -> None:
        """從 task 內部推一則 log 給前端顯示。"""
        publish_task_event(self.task_id, "log", {"level": level, "message": message})
