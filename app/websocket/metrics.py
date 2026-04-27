"""
Prometheus 指標定義。

Part 1 已經在 main.py 掛了 `app.mount("/metrics", make_asgi_app())`。
這裡只負責宣告 Part 2 新增的指標,不重複掛 endpoint。

命名慣例:  monitor_<subsystem>_<name>_<unit>
"""

from prometheus_client import Counter, Gauge

# ── WebSocket ─────────────────────────────────────────────────────────────
WS_CONNECTIONS_TOTAL = Counter(
    "monitor_ws_connections_total",
    "WebSocket 連線累計數(含歷史斷線)",
)

WS_ACTIVE_CONNECTIONS = Gauge(
    "monitor_ws_active_connections",
    "目前活躍的 WebSocket 連線數",
)

# ── Celery tasks ──────────────────────────────────────────────────────────
# 注意:Celery 有自己的 Flower + 官方 exporter,這裡只補幾個
# 業務層關心的高階指標(不重複做 worker queue depth 這類低階的)。

TASK_DISPATCHED_TOTAL = Counter(
    "monitor_task_dispatched_total",
    "透過 API 觸發的 Celery task 累計數",
    ["task_name"],
)

TASK_RESULT_TOTAL = Counter(
    "monitor_task_result_total",
    "Celery task 執行結果累計數",
    ["task_name", "state"],  # state: SUCCESS | FAILURE | RETRY
)
