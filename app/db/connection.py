"""SQLite 连接管理：建表即用，无迁移框架。"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

from app.common.errors import InfrastructureError

logger = logging.getLogger(__name__)

_SCHEMA_SQL = Path(__file__).with_name("schema.sql")


def connect(db_path: str | Path) -> sqlite3.Connection:
    """打开（必要时创建）数据库并执行建表 DDL（全部 IF NOT EXISTS）。

    返回的连接启用外键与 WAL，row_factory 为 sqlite3.Row。
    """
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # check_same_thread=False：AI 落子/解说回填在后台线程写库；
    # SQLite 编译为 serialized 模式，连接共享安全，WAL + busy_timeout 兜底写冲突。
    conn = sqlite3.connect(str(path), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")
    try:
        conn.executescript(_SCHEMA_SQL.read_text(encoding="utf-8"))
        conn.commit()
    except sqlite3.Error as exc:
        conn.close()
        raise InfrastructureError(f"数据库初始化失败: {exc}") from exc
    logger.debug("数据库已连接: %s", path)
    return conn
