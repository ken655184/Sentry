"""
AuditedTask:自訂 Celery Task base class。

功能:
1. self.ctx       取得觸發者 context(由 API 層塞入 kwargs["_ctx"])
2. self.reporter  取得對應當前 task_id 的 ProgressReporter
3. on_success / on_failure 自動把稽核寫入投遞到 audit queue(非同步)

使用方式:
    @celery_app.task(base=AuditedTask, bind=True, name="jobs.business.run_xxx")
    def run_xxx(self, arg1, *, _ctx: dict | None = None):
        self.reporter.log("開始")
        ...

    # 呼叫端:
    run_xxx.apply_async(
        args=[arg1],
        kwargs={"_ctx": {"user_id": 3, "username": "alice", "ip": "10.0.0.1"}},
    )
"""

from __future__ import annotations

from typing import Any

from celery import Task

from app.core.logging import get_logger
from app.workers.progress import ProgressReporter

logger = get_logger(__name__)


class AuditedTask(Task):
    """
    abstract = True 代表此類別本身不被註冊成 Celery task,只當 base。
    """

    abstract = True

    # ---- runtime helpers --------------------------------------------------

    @property
    def ctx(self) -> dict[str, Any]:
        """
        這次呼叫 task 的 context,由呼叫端透過 kwargs["_ctx"] 注入。
        取不到就回空 dict,避免 task function 還要額外判斷 None。
        """
        req = self.request
        kwargs = req.kwargs or {}
        return kwargs.get("_ctx") or {}

    @property
    def reporter(self) -> ProgressReporter:
        # 懶建立,保證每個 task invocation 共用同一個 reporter
        if not hasattr(self, "_reporter_cached") or self._reporter_cached is None:
            self._reporter_cached = ProgressReporter(task_id=self.request.id or "unknown")
        return self._reporter_cached

    # ---- Celery hooks -----------------------------------------------------

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """
        失敗時丟稽核寫入任務到 audit queue。
        刻意用 .apply_async 而不是直接連 DB,原因:
            - 當下可能就是 DB 掛了,同步寫會卡住
            - audit_jobs 自己有 retry,能撐過 DB 短暫抖動
        """
        from app.workers.jobs.audit_jobs import write_audit_async

        ctx = (kwargs or {}).get("_ctx") or {}
        try:
            write_audit_async.apply_async(
                kwargs=dict(
                    user_id=ctx.get("user_id"),
                    username=ctx.get("username"),
                    action=f"task.{self.name}",
                    target_type="celery_task",
                    target_id=task_id,
                    result="failure",
                    ip_address=ctx.get("ip"),
                    detail={
                        "error": str(exc),
                        "error_type": type(exc).__name__,
                    },
                ),
                queue="audit",
            )
        except Exception:  # noqa: BLE001
            # audit 投遞本身失敗不可再往上拋(會讓 retry 錯亂)
            logger.exception("on_failure.audit_enqueue_failed", extra={"task_id": task_id})
        super().on_failure(exc, task_id, args, kwargs, einfo)

    def on_success(self, retval, task_id, args, kwargs):
        """成功時寫稽核。Task 類別可設 `audit = False` 跳過(例如高頻 heartbeat)。"""
        if getattr(self, "audit", True) is False:
            return

        from app.workers.jobs.audit_jobs import write_audit_async

        ctx = (kwargs or {}).get("_ctx") or {}
        try:
            write_audit_async.apply_async(
                kwargs=dict(
                    user_id=ctx.get("user_id"),
                    username=ctx.get("username"),
                    action=f"task.{self.name}",
                    target_type="celery_task",
                    target_id=task_id,
                    result="success",
                    ip_address=ctx.get("ip"),
                    detail={"args_summary": _summarize(args, kwargs)},
                ),
                queue="audit",
            )
        except Exception:  # noqa: BLE001
            logger.exception("on_success.audit_enqueue_failed", extra={"task_id": task_id})


def _summarize(args, kwargs) -> dict[str, Any]:
    """稽核不存完整參數(可能很大),只存摘要。"""
    kw = dict(kwargs or {})
    kw.pop("_ctx", None)  # _ctx 已經在 user 欄位記錄,不重複
    return {
        "args_len": len(args or ()),
        "kwargs_keys": list(kw.keys()),
    }
