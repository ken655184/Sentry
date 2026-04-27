"""
Celery app 主設定。

對齊 Part 1:
- 使用 app.config.settings(不是 app.core.config)
- broker / backend 從 settings 讀(CELERY_BROKER_URL / CELERY_RESULT_BACKEND)
- pub/sub 另外走 REDIS_URL(跟 broker/backend 不同 db,避免互相干擾)

設計要點:
- 所有 task 模組在 include 明列,避免 Docker 環境的 autodiscover 順序問題
- 重任務走 heavy queue,稽核走 audit queue,避免互相卡住
- task_acks_late + reject_on_worker_lost:worker 崩了任務會回到 queue
- prefetch_multiplier=1:重任務環境,拿一做一,避免 worker 之間飢餓
"""

from celery import Celery
from celery.signals import task_failure, task_postrun, task_prerun
from kombu import Queue

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


celery_app = Celery(
    "monitor",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "app.workers.jobs.business_jobs",
        "app.workers.jobs.resource_jobs",
        "app.workers.jobs.audit_jobs",
        "app.workers.jobs.system_jobs",
    ],
)

celery_app.conf.update(
    # 序列化
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    # 時區
    timezone="Asia/Taipei",
    enable_utc=True,
    # 結果
    result_expires=3600,       # task result 保留 1 小時,避免 Redis 膨脹
    result_extended=True,      # 保留 task name / args,方便 Flower 與前端查
    # 執行
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    task_track_started=True,
    # 預設重試
    task_default_retry_delay=10,
    task_default_max_retries=3,
    # Queue
    task_default_queue="default",
    task_queues=(
        Queue("default", routing_key="default"),
        Queue("heavy", routing_key="heavy"),
        Queue("audit", routing_key="audit"),
    ),
    task_routes={
        "app.workers.jobs.business_jobs.*": {"queue": "heavy"},
        "app.workers.jobs.resource_jobs.*": {"queue": "heavy"},
        "app.workers.jobs.audit_jobs.*": {"queue": "audit"},
        "app.workers.jobs.system_jobs.*": {"queue": "default"},
    },
)


# ---------------------------------------------------------------------------
# 全域 signals: task 生命週期 → Redis Pub/Sub → WebSocket
# ---------------------------------------------------------------------------
# 為什麼用 signal 而不是在 task 裡手動發?
# - 任何 task 都會自動獲得這些事件,寫 task 的人不必重複貼 boilerplate
# - 失敗訊息(task_failure)在 task function return 之前就能送出
#
# 注意:task_postrun 會在成功與失敗時都觸發(state 會不同),
#       但 exception object 在 retval 位置時可能無法 JSON 序列化,
#       所以 _json_safe 做過濾。

@task_prerun.connect
def _on_task_prerun(task_id, task, args, kwargs, **_):
    from app.workers.progress import publish_task_event

    logger.info("task.prerun", extra={"task_id": task_id, "task_name": task.name})
    publish_task_event(
        task_id=task_id,
        event="started",
        payload={"task_name": task.name},
    )


@task_postrun.connect
def _on_task_postrun(task_id, task, args, kwargs, retval, state, **_):
    from app.workers.progress import publish_task_event

    logger.info(
        "task.postrun",
        extra={"task_id": task_id, "task_name": task.name, "state": state},
    )
    payload = {"task_name": task.name, "state": state}
    if state == "SUCCESS":
        payload["result"] = retval if _json_safe(retval) else str(retval)
    publish_task_event(task_id=task_id, event="finished", payload=payload)


@task_failure.connect
def _on_task_failure(task_id, exception, traceback, einfo, **_):
    from app.workers.progress import publish_task_event

    logger.error("task.failure", extra={"task_id": task_id, "error": str(exception)})
    publish_task_event(
        task_id=task_id,
        event="failed",
        payload={
            "error": str(exception),
            "error_type": type(exception).__name__,
        },
    )


def _json_safe(value) -> bool:
    """粗略判斷 retval 能否被 JSON 序列化,避免 signal handler 自己炸掉。"""
    import json

    try:
        json.dumps(value)
        return True
    except (TypeError, ValueError):
        return False
