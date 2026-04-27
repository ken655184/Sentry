"""
Task 觸發 / 查詢 API。

PUT  /api/v1/tasks/dispatch           觸發一個 job
GET  /api/v1/tasks/{task_id}/status   查詢 task 狀態
POST /api/v1/tasks/{task_id}/cancel   取消 task(若還在 queue 中)
GET  /api/v1/tasks/ping               健康探針(確認 Celery 有回應)

設計:
- 所有觸發端點都需要登入(_ctx 自動從當前 user 組裝,不用前端帶)
- task_id 回給前端後,前端自己透過 WebSocket subscribe task:{task_id} 監聽進度
- 查詢狀態走 Celery result backend(Redis),不走 DB
"""

from __future__ import annotations

from typing import Any

from celery.result import AsyncResult
from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from app.auth.audit import get_client_ip, write_audit
from app.auth.dependencies import get_current_user, require_permission
from app.auth.models import User
from app.auth.permissions import Permission
from app.core.response import ok
from app.websocket.metrics import TASK_DISPATCHED_TOTAL
from app.workers.celery_app import celery_app
from app.workers.jobs.business_jobs import run_job, run_batch
from app.workers.jobs.resource_jobs import scan_path, read_file
from app.workers.jobs.system_jobs import ping as ping_worker

from fastapi import Request

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────

class DispatchRequest(BaseModel):
    job_key: str = Field(..., description="業務 registry key,例: example.echo")
    params: dict[str, Any] = Field(default_factory=dict)


class BatchDispatchRequest(BaseModel):
    job_key: str
    items: list[dict[str, Any]] = Field(..., min_length=1)


class ScanRequest(BaseModel):
    path: str
    pattern: str = "*"
    recursive: bool = True


class ReadFileRequest(BaseModel):
    file_path: str


# ── 輔助 ──────────────────────────────────────────────────────────────────

def _build_ctx(request: Request, user: User) -> dict:
    """把當前 user 組成 _ctx 傳給 task,供稽核使用。"""
    return {
        "user_id": user.id,
        "username": user.username,
        "ip": get_client_ip(request),
    }


def _task_response(task_id: str, task_name: str) -> dict:
    TASK_DISPATCHED_TOTAL.labels(task_name=task_name).inc()
    return {
        "task_id": task_id,
        "task_name": task_name,
        "ws_room": f"task:{task_id}",
        "hint": "subscribe to ws_room via WebSocket to receive progress",
    }


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.post(
    "/dispatch",
    summary="觸發業務 job",
)
async def dispatch_job(
    body: DispatchRequest,
    request: Request,
    user: User = Depends(require_permission(Permission.TEST_EXECUTE)),
):
    ctx = _build_ctx(request, user)
    result = run_job.apply_async(
        args=[body.job_key, body.params],
        kwargs={"_ctx": ctx},
    )
    return ok(_task_response(result.id, "jobs.business.run_job"))


@router.post("/batch", summary="批次執行業務 job")
async def dispatch_batch(
    body: BatchDispatchRequest,
    request: Request,
    user: User = Depends(require_permission(Permission.TEST_EXECUTE)),
):
    ctx = _build_ctx(request, user)
    result = run_batch.apply_async(
        args=[body.job_key, body.items],
        kwargs={"_ctx": ctx},
    )
    return ok(_task_response(result.id, "jobs.business.batch"))


@router.post("/scan", summary="掃描檔案路徑")
async def dispatch_scan(
    body: ScanRequest,
    request: Request,
    user: User = Depends(require_permission(Permission.SYSTEM_CONFIG)),
):
    ctx = _build_ctx(request, user)
    result = scan_path.apply_async(
        args=[body.path, body.pattern, body.recursive],
        kwargs={"_ctx": ctx},
    )
    return ok(_task_response(result.id, "jobs.resource.scan_path"))


@router.post("/read-file", summary="讀取檔案 metadata")
async def dispatch_read_file(
    body: ReadFileRequest,
    request: Request,
    user: User = Depends(require_permission(Permission.SYSTEM_CONFIG)),
):
    ctx = _build_ctx(request, user)
    result = read_file.apply_async(
        args=[body.file_path],
        kwargs={"_ctx": ctx},
    )
    return ok(_task_response(result.id, "jobs.resource.read_file"))


@router.get("/{task_id}/status", summary="查詢 task 狀態")
async def get_task_status(
    task_id: str,
    user: User = Depends(get_current_user),
):
    r: AsyncResult = AsyncResult(task_id, app=celery_app)
    data: dict[str, Any] = {
        "task_id": task_id,
        "state": r.state,        # PENDING / STARTED / SUCCESS / FAILURE / RETRY
        "ready": r.ready(),
        "successful": r.successful() if r.ready() else None,
    }
    if r.ready():
        if r.successful():
            data["result"] = r.result
        else:
            data["error"] = str(r.result)
    return ok(data)


@router.post("/{task_id}/cancel", summary="取消 task(僅 queue 中有效)")
async def cancel_task(
    task_id: str,
    user: User = Depends(require_permission(Permission.SYSTEM_CONFIG)),
):
    celery_app.control.revoke(task_id, terminate=False)
    return ok({"task_id": task_id, "action": "revoked"})


@router.get("/ping", summary="確認 Celery worker 有回應")
async def celery_ping(
    user: User = Depends(require_permission(Permission.SYSTEM_CONFIG)),
):
    result = ping_worker.apply_async(queue="default")
    try:
        pong = result.get(timeout=3)
        return ok({"pong": pong, "latency_ms": None})
    except Exception as exc:
        return ok({"pong": None, "error": str(exc)})
