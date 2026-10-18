"""日志配置：输出到 runtime/log/，按天轮转。

分级约定：
- DEBUG：搜索节点数、LLM 请求体（脱敏）；
- INFO：对局开始/结束、模型切换；
- WARNING：LLM 超时降级；
- ERROR：未捕获异常。

控制台输出走独立线程：Windows 控制台进入“选择文本”(QuickEdit) 模式时，
WriteConsoleW 会一直阻塞；若后台线程直接打印，AI 走棋会被一起卡住。
"""

from __future__ import annotations

import atexit
import logging
import queue
from logging.handlers import QueueHandler, QueueListener, TimedRotatingFileHandler

from app.common.paths import runtime_dir

_FMT = "%(asctime)s %(levelname)-7s [%(threadName)s] %(name)s: %(message)s"

_listener: QueueListener | None = None


def setup_logging(level: str = "INFO") -> None:
    """初始化根 logger：文件 + 非阻塞控制台。"""
    global _listener

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
    root.handlers.clear()

    formatter = logging.Formatter(_FMT)

    # 文件处理器直接挂在根 logger 上：先落盘，且不会被控制台阻塞连累
    log_dir = runtime_dir("log")
    file_handler = TimedRotatingFileHandler(
        log_dir / "app.log",
        when="midnight",
        backupCount=14,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # 控制台处理器放入队列，由单独线程消费；业务线程调用 logging 不会阻塞
    console = logging.StreamHandler()
    console.setFormatter(formatter)
    log_queue: queue.SimpleQueue[logging.LogRecord] = queue.SimpleQueue()
    root.addHandler(QueueHandler(log_queue))

    if _listener is not None:
        _listener.stop()
    _listener = QueueListener(log_queue, console, respect_handler_level=True)
    _listener.start()
    atexit.register(_listener.stop)
