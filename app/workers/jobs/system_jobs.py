"""
系統層級 task:心跳、過期稽核清理、health 探針。

這些 task 由 Celery beat 排程(見 celery_beat.py)。
繼承 AuditedTask 沒有必要(heartbeat 寫稽核會把表灌爆),所以用基本 Task。
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import delete

from app.auth.database import AsyncSessionLocal
from app.auth.models import AuditLog
from app.core.logging import get_logger
from app.workers.celery_app import celery_app
from app.workers.progress import publish_system_event

logger = get_logger(__name__)


@celery_app.task(name="jobs.system.heartbeat")
def heartbeat() -> dict[str, Any]:
    """
    Worker 每隔 N 秒發一次心跳,讓前端看到整體節點健康。
    同時廣播到 system:events channel,管理員面板可顯示 worker 狀態。
    """
    now = datetime.now(timezone.utc).isoformat()
    publish_system_event("heartbeat", {"ts": now})
    return {"ts": now, "ok": True}


@celery_app.task(name="jobs.system.cleanup_old_audit_logs")
def cleanup_old_audit_logs(days: int | None = None) -> dict[str, Any]:
    """
    清理超過保留期限的稽核紀錄。

    注意:稽核紀錄通常有法遵保留要求,刪除前請先備份到冷儲存。
    這個 task **不負責備份**,只做刪除。
    """
    # 預設從 settings 取;若沒設就給一個保守值(180 天)
    from app.config import settings
    retention = days if days is not None else getattr(settings, "AUDIT_LOG_RETENTION_DAYS", 180)
    if retention <= 0:
        return {"deleted": 0, "skipped": True, "reason": "retention<=0"}

    cutoff = datetime.now(timezone.utc) - timedelta(days=retention)
    deleted = asyncio.run(_do_cleanup(cutoff))
    logger.info(
        "cleanup_old_audit_logs",
        extra={"deleted": deleted, "cutoff": cutoff.isoformat()},
    )
    return {"deleted": deleted, "cutoff": cutoff.isoformat()}


async def _do_cleanup(cutoff: datetime) -> int:
    async with AsyncSessionLocal() as session:
        # 用 bulk delete(不 load 物件),避免幾十萬列進 identity map
        stmt = delete(AuditLog).where(AuditLog.created_at < cutoff)
        result = await session.execute(stmt)
        await session.commit()
        return int(result.rowcount or 0)


@celery_app.task(name="jobs.system.ping")
def ping() -> str:
    """
    最簡單的健康探針。API 層可透過 `.delay().get(timeout=2)` 確認 Celery 回應。
    """
    return "pong"
