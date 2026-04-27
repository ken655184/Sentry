"""
檔案資源相關 task。

目的:對 server 上散落的資料目錄做掃描、metadata 讀取。
實際檔案 IO 邏輯在 app.repositories.filesystem.loader,這裡只做 Celery 包裝。
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.repositories.filesystem import loader as fs_loader
from app.workers.base import AuditedTask
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(
    base=AuditedTask,
    bind=True,
    name="jobs.resource.scan_path",
    max_retries=2,
    default_retry_delay=20,
)
def scan_path(
    self,
    path: str,
    pattern: str = "*",
    recursive: bool = True,
    *,
    _ctx: dict | None = None,
):
    """
    掃描指定路徑,回傳摘要(不回完整檔案列表,避免 result 太大)。
    完整明細透過 reporter.log 推到前端。

    錯誤策略:
        FileNotFoundError / PermissionError → 轉 ValueError 不 retry
            (路徑錯 / 權限不足,重試沒意義)
        其他 IOError → retry,通常是暫時性(NFS 斷、disk 忙)
    """
    self.reporter.log(f"開始掃描: {path} (pattern={pattern}, recursive={recursive})")
    try:
        return fs_loader.scan(
            path=path,
            pattern=pattern,
            recursive=recursive,
            reporter=self.reporter,
        )
    except FileNotFoundError as exc:
        raise ValueError(f"Path not found: {path}") from exc
    except PermissionError as exc:
        raise ValueError(f"Permission denied: {path}") from exc
    except Exception as exc:
        logger.exception("resource.scan_path.failed", extra={"path": path})
        raise self.retry(exc=exc, countdown=20 * (2 ** self.request.retries))


@celery_app.task(
    base=AuditedTask,
    bind=True,
    name="jobs.resource.read_file",
)
def read_file(self, file_path: str, *, _ctx: dict | None = None) -> dict[str, Any]:
    """
    讀取單一檔案的 metadata 與前 N 行。
    完整內容請走 FastAPI streaming response,不要走 Celery result backend。
    """
    self.reporter.log(f"讀取檔案: {file_path}")
    return fs_loader.read_meta(file_path, reporter=self.reporter)
