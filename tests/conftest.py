"""pytest 公共 fixture。"""

from __future__ import annotations

import pytest

from app.core.gomoku.board import GomokuBoard


@pytest.fixture
def board() -> GomokuBoard:
    """空 15×15 棋盘。"""
    return GomokuBoard()


def make_board(size: int = 15) -> GomokuBoard:
    return GomokuBoard(size)
