"""后台任务封装与线程安全回调。

约定：后台线程绝不直接操作 Tkinter 控件；
所有结果经 queue.Queue + root.after() 送回主线程。
"""

from __future__ import annotations

import logging
import queue
import threading
from collections.abc import Callable
from typing import Any, Protocol

logger = logging.getLogger(__name__)


class AfterFunc(Protocol):
    """tkinter root.after 的最小签名：after(毫秒, 回调)。"""

    def __call__(self, ms: int, func: Callable[[], None]) -> Any: ...


def run_in_background(
    fn: Callable[[], Any],
    on_error: Callable[[BaseException], None] | None = None,
) -> threading.Thread:
    """在守护线程中执行 fn；未捕获异常记 ERROR 并回调 on_error。"""

    def _worker() -> None:
        try:
            fn()
        except BaseException as exc:  # noqa: BLE001 - 后台线程兜底
            logger.exception("后台任务异常: %s", exc)
            if on_error is not None:
                try:
                    on_error(exc)
                except BaseException:  # noqa: BLE001
                    logger.exception("on_error 回调自身异常")

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    return thread


class QueuePoller:
    """主线程轮询队列的辅助器。

    用法（UI 主线程）::

        poller = QueuePoller(q)
        poller.start(root.after, lambda item: label.config(text=str(item)))
        ...
        poller.stop()
    """

    def __init__(self, q: queue.Queue[Any], poll_ms: int = 50) -> None:
        self._q = q
        self._poll_ms = poll_ms
        self._running = threading.Event()
        self._after: AfterFunc | None = None
        self._consume: Callable[[Any], None] | None = None

    def start(self, after: AfterFunc, consume: Callable[[Any], None]) -> None:
        """注册 tkinter root.after 与消费回调，开始轮询。"""
        self._after = after
        self._consume = consume
        self._running.set()
        self._loop()

    def _loop(self) -> None:
        if not self._running.is_set() or self._after is None or self._consume is None:
            return
        try:
            while True:
                item = self._q.get_nowait()
                try:
                    self._consume(item)
                except Exception:  # noqa: BLE001 - 单个事件出错不能停掉轮询
                    logger.exception("事件处理异常，已跳过: %r", item)
        except queue.Empty:
            pass
        if self._running.is_set():
            self._after(self._poll_ms, self._loop)

    def stop(self) -> None:
        self._running.clear()
