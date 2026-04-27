"""
稽核日誌寫入 task。

為什麼要非同步寫稽核?
- API 每次操作都要寫稽核,同步寫會吃掉 response latency
- DB 短暫抖動時,同步寫會讓使用者看到失敗(但業務已經完成)
- 走 audit queue + retry,寫失敗會自己重試,最終一致

重要:這個 task 故意 **不繼承 AuditedTask**。
    理由:若繼承,寫稽核失敗會觸發 on_failure → 又寫稽核 → 又失敗 → 無限遞迴。

Async ↔ Sync 橋接:
    Part 1 的 write_audit 是 async(對齊 Part 1 統一用 AsyncSession)。
    Celery 預設是 sync worker(prefork),所以這裡用 asyncio.run 把 async 包一層。
    每個 task 呼叫會建立一個新的 event loop — 對於短任務(寫一筆 DB)成本可接受,
    真正高頻時 bulk_write 會把多筆合併成一次呼叫,攤平成本。
"""

from __future__ import annotations

import asyncio
from typing import Any

from app.auth.audit import write_audit
from app.auth.database import AsyncSessionLocal
from app.auth.models import AuditLog
from app.core.logging import get_logger
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(
    bind=True,
    name="jobs.audit.write_audit_async",
    max_retries=5,
    default_retry_delay=5,
    autoretry_for=(Exception,),
    retry_backoff=True,       # 指數退避,避免重試風暴
    retry_backoff_max=300,
    retry_jitter=True,
)
def write_audit_async(
    self,
    *,
    user_id: int | None,
    username: str | None,
    action: str,
    target_type: str | None = None,
    target_id: str | None = None,
    result: str = "success",
    ip_address: str | None = None,
    detail: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """
    寫一筆稽核紀錄。

    欄位對齊 Part 1 的 AuditLog model:
        target_type / target_id / ip_address / detail(JSON 字串)/ created_at

    注意:我們不直接用 Part 1 的 write_audit — 因為它要求傳入 User ORM 物件,
    但 Celery context 裡沒有 User,只有 user_id/username 字串。直接寫 ORM 更乾淨。
    """
    asyncio.run(_do_write_single(
        user_id=user_id,
        username=username,
        action=action,
        target_type=target_type,
        target_id=target_id,
        result=result,
        ip_address=ip_address,
        detail=detail,
    ))
    return {"ok": True, "action": action}


async def _do_write_single(
    *,
    user_id: int | None,
    username: str | None,
    action: str,
    target_type: str | None,
    target_id: str | None,
    result: str,
    ip_address: str | None,
    detail: dict[str, Any] | None,
) -> None:
    import json

    async with AsyncSessionLocal() as session:
        log = AuditLog(
            user_id=user_id,
            username=username,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            result=result,
            ip_address=ip_address,
            detail=json.dumps(detail, ensure_ascii=False) if detail else None,
        )
        session.add(log)
        try:
            await session.commit()
        except Exception:
            await session.rollback()
            raise


@celery_app.task(
    bind=True,
    name="jobs.audit.bulk_write",
    max_retries=3,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_jitter=True,
)
def bulk_write_audit(self, records: list[dict[str, Any]]) -> dict[str, int]:
    """
    批次寫稽核,適合高頻操作彙整後一次 flush。
    單筆錯誤不影響其他,回傳 good / bad 筆數。
    """
    return asyncio.run(_do_bulk_write(records))


async def _do_bulk_write(records: list[dict[str, Any]]) -> dict[str, int]:
    import json

    good = 0
    bad = 0

    async with AsyncSessionLocal() as session:
        for r in records:
            try:
                r = dict(r)
                detail = r.pop("detail", None)
                session.add(AuditLog(
                    user_id=r.get("user_id"),
                    username=r.get("username"),
                    action=r.get("action", "unknown"),
                    target_type=r.get("target_type"),
                    target_id=str(r["target_id"]) if r.get("target_id") is not None else None,
                    result=r.get("result", "success"),
                    ip_address=r.get("ip_address"),
                    detail=json.dumps(detail, ensure_ascii=False) if detail else None,
                ))
                good += 1
            except Exception:  # noqa: BLE001
                logger.exception("bulk_write_audit.bad_record")
                bad += 1
        try:
            await session.commit()
        except Exception:
            await session.rollback()
            raise

    return {"inserted": good, "rejected": bad}
