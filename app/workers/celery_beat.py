"""
Celery beat 排程設定。

啟動指令:
    celery -A app.workers.celery_app:celery_app beat -l info

刻意獨立一檔,讓 ops 調整排程不必動主設定。
"""

from celery.schedules import crontab

from app.workers.celery_app import celery_app

celery_app.conf.beat_schedule = {
    # 每 30 秒心跳,讓前端管理面板知道 worker 還活著
    "system-heartbeat": {
        "task": "jobs.system.heartbeat",
        "schedule": 30.0,
        "options": {"queue": "default"},
    },
    # 每天凌晨 3:00 清理過期稽核紀錄
    "cleanup-audit-logs": {
        "task": "jobs.system.cleanup_old_audit_logs",
        "schedule": crontab(hour=3, minute=0),
        "options": {"queue": "audit"},
    },
}
