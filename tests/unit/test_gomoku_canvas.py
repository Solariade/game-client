"""GomokuCanvas 建议落子 / 预选虚拟棋子单测。"""

from __future__ import annotations

import tkinter as tk

import pytest

from app.core.base_game import Move
from app.core.gomoku.board import GomokuBoard
from app.ui import theme
from app.ui.boards.gomoku_canvas import HINT_TAG, PREVIEW_TAG, GomokuCanvas

STAR_OVALS = 5  # 五个星位圆点


@pytest.fixture()
def canvas(tk_root: tk.Tk):
    yield GomokuCanvas(tk_root, on_click=None)


def _items(canvas: GomokuCanvas, tag: str) -> tuple[int, ...]:
    return canvas.find_withtag(tag)


def _ovals(canvas: GomokuCanvas, tag: str | None = None) -> list[int]:
    items = canvas.find_all() if tag is None else _items(canvas, tag)
    return [item for item in items if canvas.type(item) == "oval"]


def _fills(canvas: GomokuCanvas, tag: str) -> list[str]:
    return [canvas.itemcget(item, "fill") for item in _ovals(canvas, tag)]


def _outlines(canvas: GomokuCanvas, tag: str) -> list[str]:
    return [canvas.itemcget(item, "outline") for item in _ovals(canvas, tag)]


def test_show_hint_sets_property_and_draws(canvas: GomokuCanvas) -> None:
    canvas.show_hint(Move(7, 7), color=1)
    assert canvas.hint_move == Move(7, 7)
    # 虚线光环 + 缩小的建议棋子 = 2 个圆，无角标文字
    assert len(_ovals(canvas, HINT_TAG)) == 2
    assert len(_items(canvas, HINT_TAG)) == 2
    assert len(_ovals(canvas)) == STAR_OVALS + 2


def test_show_hint_replaces_previous(canvas: GomokuCanvas) -> None:
    canvas.show_hint(Move(7, 7), color=1)
    canvas.show_hint(Move(8, 8), color=1)
    assert canvas.hint_move == Move(8, 8)
    assert len(_items(canvas, HINT_TAG)) == 2  # 旧的被移除，不是叠加


def test_hint_color_follows_user_color(canvas: GomokuCanvas) -> None:
    canvas.show_hint(Move(7, 7), color=1)
    black_fills = _fills(canvas, HINT_TAG)
    black_outlines = _outlines(canvas, HINT_TAG)
    canvas.show_hint(Move(8, 8), color=-1)
    white_fills = _fills(canvas, HINT_TAG)
    white_outlines = _outlines(canvas, HINT_TAG)

    assert theme.BLACK_STONE in black_fills  # 黑棋黑色填充
    assert theme.WHITE_STONE in white_fills  # 白棋白色填充
    assert theme.HINT_RING in black_outlines  # 建议棋子绿色描边 / 外层光环
    assert theme.HINT_RING in white_outlines


def test_real_stone_outline_matches_color(canvas: GomokuCanvas) -> None:
    board = GomokuBoard()
    board.place(Move(7, 7), 1)
    board.place(Move(8, 8), -1)
    canvas.sync_board(board)

    stone_outlines = _outlines(canvas, "all")
    assert theme.BLACK_STONE_EDGE in stone_outlines
    assert theme.WHITE_STONE_EDGE in stone_outlines


def test_clear_hint_removes_only_hint(canvas: GomokuCanvas) -> None:
    board = GomokuBoard()
    board.place(Move(7, 7), 1)
    canvas.sync_board(board, last_move=Move(7, 7))
    with_stone = len(_ovals(canvas))

    canvas.show_hint(Move(8, 8), color=-1)
    canvas.clear_hint()
    assert canvas.hint_move is None
    assert len(_ovals(canvas)) == with_stone  # 真实棋子不受影响


def test_sync_board_discards_hint_and_pending(canvas: GomokuCanvas) -> None:
    canvas.show_hint(Move(7, 7), color=1)
    canvas.show_pending(Move(8, 8), color=1)
    board = GomokuBoard()
    board.place(Move(0, 0), 1)
    canvas.sync_board(board, last_move=Move(0, 0))
    assert canvas.hint_move is None  # 棋盘变化后旧提示作废
    assert canvas.pending_move is None  # 预选也一并作废


# ---- 预选虚拟棋子（第一次点击） ----


def test_show_pending_sets_property_and_draws(canvas: GomokuCanvas) -> None:
    canvas.show_pending(Move(5, 5), color=1)
    assert canvas.pending_move == Move(5, 5)
    # 外圈 + 内圈 + 中心黑点 = 3 个圆，无文字
    assert len(_ovals(canvas, PREVIEW_TAG)) == 3
    assert len(_items(canvas, PREVIEW_TAG)) == 3
    assert theme.BLACK_STONE in _fills(canvas, PREVIEW_TAG)


def test_show_pending_replaces_previous(canvas: GomokuCanvas) -> None:
    canvas.show_pending(Move(5, 5), color=1)
    canvas.show_pending(Move(6, 6), color=-1)
    assert canvas.pending_move == Move(6, 6)
    assert len(_items(canvas, PREVIEW_TAG)) == 3  # 旧的被移除
    assert theme.WHITE_STONE in _fills(canvas, PREVIEW_TAG)


def test_pending_on_hint_point_hides_hint(canvas: GomokuCanvas) -> None:
    canvas.show_hint(Move(7, 7), color=1)
    canvas.show_pending(Move(7, 7), color=1)
    assert canvas.pending_move == Move(7, 7)
    assert canvas.hint_move is None  # 两层虚拟子不重叠


def test_pending_elsewhere_keeps_hint(canvas: GomokuCanvas) -> None:
    canvas.show_hint(Move(7, 7), color=1)
    canvas.show_pending(Move(8, 8), color=1)
    assert canvas.hint_move == Move(7, 7)
    assert canvas.pending_move == Move(8, 8)


def test_clear_pending_removes_only_preview(canvas: GomokuCanvas) -> None:
    board = GomokuBoard()
    board.place(Move(7, 7), 1)
    canvas.sync_board(board, last_move=Move(7, 7))
    with_stone = len(_ovals(canvas))

    canvas.show_hint(Move(8, 8), color=1)
    canvas.show_pending(Move(9, 9), color=1)
    canvas.clear_pending()
    assert canvas.pending_move is None
    assert canvas.hint_move == Move(8, 8)  # 建议子保留
    assert len(_items(canvas, PREVIEW_TAG)) == 0
    assert len(_ovals(canvas)) == with_stone + 2  # 只少了预选虚拟子，建议子保留
