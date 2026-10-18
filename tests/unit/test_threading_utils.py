"""QueuePoller 单测：事件处理异常不能中断后续轮询。"""

from __future__ import annotations

import queue
from typing import Any

from app.common.threading_utils import QueuePoller


def test_consume_error_does_not_stop_polling() -> None:
    q: queue.Queue[Any] = queue.Queue()
    seen: list[Any] = []
    scheduled: list[Any] = []

    def consume(item: Any) -> None:
        seen.append(item)
        if item == "bad":
            raise RuntimeError("boom")

    poller = QueuePoller(q, poll_ms=60)
    q.put("bad")
    q.put("ok")
    poller.start(lambda _ms, func: scheduled.append(func), consume)

    assert seen == ["bad", "ok"]  # 出错事件被跳过，后续事件照常处理
    assert len(scheduled) == 1  # 仍然安排了下一次轮询
    poller.stop()
