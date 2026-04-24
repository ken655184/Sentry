"""稽核日誌工具"""
import json
from typing import Any

from fastapi import Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.database import AsyncSessionLocal
from app.auth.models import AuditLog, User


async def write_audit(
    *,
    user: User | None,
    action: str,
    target_type: str | None = None,
    target_id: str | Any = None,
    result: str = "success",
    ip_address: str | None = None,
    detail: dict | None = None,
    db: AsyncSession | None = None,
) -> None:
    """寫入一筆稽核日誌 - 失敗不影響主流程"""
    log = AuditLog(
        user_id=user.id if user else None,
        username=user.username if user else None,
        action=action,
        target_type=target_type,
        target_id=str(target_id) if target_id is not None else None,
        result=result,
        ip_address=ip_address,
        detail=json.dumps(detail, ensure_ascii=False) if detail else None,
    )

    if db is not None:
        db.add(log)
        try:
            await db.commit()
        except Exception:
            await db.rollback()
        return

    async with AsyncSessionLocal() as session:
        session.add(log)
        try:
            await session.commit()
        except Exception:
            await session.rollback()


def get_client_ip(request: Request) -> str | None:
    """取得真實 client IP(考慮 proxy)"""
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None
