"""
Unit tests: workers.progress

因為是 unit test,Redis 用 fakeredis mock 掉,不需要真的連線。
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


# ── helpers ───────────────────────────────────────────────────────────────

def _make_fake_redis():
    """回傳一個 fakeredis-like mock,讓 pipeline().execute() 不報錯。"""
    fake = MagicMock()
    pipe = MagicMock()
    pipe.execute.return_value = [1, 1]
    fake.pipeline.return_value = pipe
    return fake


# ── publish_task_event ────────────────────────────────────────────────────

@patch("app.workers.progress._get_redis")
def test_publish_task_event_calls_pipeline(mock_get_redis):
    fake = _make_fake_redis()
    mock_get_redis.return_value = fake

    from app.workers.progress import publish_task_event
    publish_task_event("abc-123", "started", {"task_name": "jobs.business.run_job"})

    pipe = fake.pipeline.return_value
    assert pipe.publish.call_count == 2   # task:abc-123 + tasks:broadcast
    pipe.execute.assert_called_once()


@patch("app.workers.progress._get_redis")
def test_publish_task_event_redis_error_does_not_raise(mock_get_redis):
    """Redis 掛掉時不應讓 task 本身失敗。"""
    import redis

    fake = _make_fake_redis()
    fake.pipeline.return_value.execute.side_effect = redis.RedisError("conn refused")
    mock_get_redis.return_value = fake

    from app.workers.progress import publish_task_event
    # 不應拋出任何例外
    publish_task_event("abc-123", "started")


# ── ProgressReporter ──────────────────────────────────────────────────────

@patch("app.workers.progress._get_redis")
def test_progress_reporter_throttle(mock_get_redis):
    """相同百分比不應重複送訊息。"""
    fake = _make_fake_redis()
    mock_get_redis.return_value = fake

    from app.workers.progress import ProgressReporter

    r = ProgressReporter("task-1", total=100)
    with r:
        r.update(1)   # 1%
        r.update(1)   # 還是 1%,應該被節流
        r.update(2)   # 2%,送出

    pipe = fake.pipeline.return_value
    # __enter__ 送 1 次 + update(1) 1 次 + update(2) 1 次 = 3 次 publish pair
    # (update(1) 第二次被 throttle,不算)
    assert pipe.execute.call_count == 3


@patch("app.workers.progress._get_redis")
def test_progress_reporter_log(mock_get_redis):
    fake = _make_fake_redis()
    mock_get_redis.return_value = fake

    from app.workers.progress import ProgressReporter

    r = ProgressReporter("task-2")
    r.log("hello", level="warning")

    pipe = fake.pipeline.return_value
    # log 呼叫 publish_task_event,publish 應被呼叫兩次(task channel + broadcast)
    assert pipe.publish.call_count == 2
    call_args = [str(c) for c in pipe.publish.call_args_list]
    assert any("task:task-2" in s for s in call_args)
