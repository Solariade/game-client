"""pytest 公共 fixture。"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Iterator

import pytest

from app.core.gomoku.board import GomokuBoard


@pytest.fixture
def board() -> GomokuBoard:
    """空 15×15 棋盘。"""
    return GomokuBoard()


@pytest.fixture
def tk_root() -> Iterator[tk.Tk]:
    """创建隐藏的 Tk 根窗口；Tcl/Tk 不可用时跳过 GUI 测试。

    GitHub Actions 的 Windows runner 偶发缺少 Tcl/Tk 资源文件，
    此时跳过而不是让整个测试套件报错。
    """
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        pytest.skip(f"Tk 不可用，跳过 GUI 测试：{exc}")
    root.withdraw()
    try:
        yield root
    finally:
        root.destroy()


def make_board(size: int = 15) -> GomokuBoard:
    return GomokuBoard(size)
