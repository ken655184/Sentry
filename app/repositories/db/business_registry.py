"""
業務模組 registry(留空介面,供外部 Python 模組接入)。

你們的業務邏輯是一組外部 Python 模組 — 為了不把外部耦合到 Celery,
採用 key → callable registry:業務端在自己的模組初始化時呼叫
`register("report.daily", fn)`,Task 層(business_jobs.run_job)只認 key。

callable signature:
    def handler(*, params: dict, reporter, ctx: dict) -> Any: ...

實際業務函式等你們接進來時補上。此檔目前只提供空 registry 與一個
用於健康驗證的 example.echo handler(prod 可拿掉)。
"""

from __future__ import annotations

from typing import Any, Protocol


class BusinessHandler(Protocol):
    def __call__(self, *, params: dict, reporter: Any, ctx: dict) -> Any: ...


_registry: dict[str, BusinessHandler] = {}


def register(key: str, handler: BusinessHandler) -> None:
    """註冊一個業務 handler。重複註冊會覆蓋(dev 方便)。"""
    _registry[key] = handler


def get(key: str) -> BusinessHandler:
    """取得 handler。找不到丟 KeyError。由上層 task 轉成 ValueError 避免重試。"""
    if key not in _registry:
        raise KeyError(key)
    return _registry[key]


def keys() -> list[str]:
    return sorted(_registry.keys())


# --- 範例 handler(驗證用,生產可刪)------------------------------------
def _example_echo(*, params: dict, reporter: Any, ctx: dict) -> dict:
    reporter.log(f"echo received: {params}")
    reporter.update(1)
    return {"echo": params, "by": ctx.get("username")}


register("example.echo", _example_echo)
