"""
業務模組相關 task。

這些 task 是 Celery 與業務模組之間的薄薄一層 wrapper:
    business_jobs.run_job  --lookup--> business_registry.get(key)  --call--> 外部業務 handler

為什麼不讓業務模組直接宣告成 Celery task?
- 業務模組屬於你們自己維護的外部程式碼,不該被 Celery / infra 綁住
- 透過 registry 註冊,未來更換執行引擎(thread pool / RQ / dramatiq)也只動這層
- 新增業務 job 不必改 Celery 設定,只要在業務端 register("xxx", fn)

Task 命名規範:jobs.business.<verb_noun>
"""

from __future__ import annotations

from typing import Any

from app.core.logging import get_logger
from app.repositories.db import business_registry
from app.workers.base import AuditedTask
from app.workers.celery_app import celery_app

logger = get_logger(__name__)


@celery_app.task(
    base=AuditedTask,
    bind=True,
    name="jobs.business.run_job",
    max_retries=2,
    default_retry_delay=30,
)
def run_job(
    self,
    job_key: str,
    params: dict[str, Any] | None = None,
    *,
    _ctx: dict | None = None,
):
    """
    通用業務模組執行入口。

    參數:
        job_key: 在 business_registry 登錄的 key(例:"report.daily", "scan.assets")
        params:  傳給業務函式的參數
        _ctx:    觸發者 context(API 層自動注入)

    錯誤處理策略:
        - 未知 job_key → ValueError(不 retry,是寫死的 bug,重試也沒用)
        - 其他例外 → 交由 Celery retry(指數退避),次數用盡才真正失敗
    """
    params = params or {}
    self.reporter.log(f"準備執行業務任務: {job_key}")

    try:
        fn = business_registry.get(job_key)
    except KeyError:
        # 不 retry:未知 job 等同於設定錯誤,retry 只會拖慢失敗回饋
        raise ValueError(f"Unknown business job: {job_key}")

    try:
        result = fn(params=params, reporter=self.reporter, ctx=_ctx or {})
        return {"job_key": job_key, "ok": True, "result": result}
    except Exception as exc:
        logger.exception("business.run_job.failed", extra={"job_key": job_key})
        # countdown 指數退避,避免短暫 flap 引發重試風暴
        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries))


@celery_app.task(
    base=AuditedTask,
    bind=True,
    name="jobs.business.batch",
    max_retries=1,
)
def run_batch(
    self,
    job_key: str,
    items: list[dict],
    *,
    _ctx: dict | None = None,
):
    """
    同一個業務 handler 套用到一批 item。
    常見用途:對一組目標跑同一個分析流程(例:對 100 台機器跑檢查)。

    刻意用同步 for loop,沒有用 Celery group() 做 fan-out,原因:
    - 大多數業務流程彼此有順序或共用資源(DB 連線、檔案 lock)
    - fan-out 後要統整進度很囉嗦;要 fan-out 可以在業務 handler 內部自己做
    - 批次整體成功 / 失敗比例容易彙整回報
    """
    try:
        fn = business_registry.get(job_key)
    except KeyError:
        raise ValueError(f"Unknown business job: {job_key}")

    total = len(items)
    self.reporter.log(f"批次執行 {job_key},共 {total} 項")
    results: list[dict] = []
    failed = 0

    # reporter 會在同一個 with block 內節流,這邊不用自己節流
    with self.reporter as p:  # 會發一則 progress=0 當開場
        p.total = total
        for idx, item in enumerate(items, 1):
            p.update(idx, note=f"處理中: {item.get('name', idx)}")
            try:
                res = fn(params=item, reporter=self.reporter, ctx=_ctx or {})
                results.append({"ok": True, "item": item, "result": res})
            except Exception as exc:  # noqa: BLE001
                # 單筆失敗不中斷整批 — 批次任務的語意就是容忍部分失敗
                failed += 1
                self.reporter.log(f"第 {idx} 項失敗: {exc}", level="error")
                results.append({"ok": False, "item": item, "error": str(exc)})

    return {
        "job_key": job_key,
        "total": total,
        "failed": failed,
        "succeeded": total - failed,
        "results": results,
    }
