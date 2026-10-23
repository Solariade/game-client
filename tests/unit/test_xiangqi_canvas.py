"""XiangqiCanvas 渲染与交互坐标单测（Tk 不可用时自动跳过）。"""

from __future__ import annotations

import tkinter as tk
import tkinter.font as tkfont
from types import SimpleNamespace

from app.core.base_game import Move
from app.core.xiangqi import rules
from app.core.xiangqi.board import XiangqiBoard
from app.ui import theme
from app.ui.boards.xiangqi_canvas import (
    CHECK_TAG,
    HINT_TAG,
    LAST_TAG,
    PENDING_TAG,
    PIECE_TAG,
    SELECT_TAG,
    WIN_TAG,
    XiangqiCanvas,
)

# 炮二平五（红）与黑马 8 进 7（黑）
H2E2 = (7, 7, 7, 4)
H9G7 = (0, 7, 2, 6)


def make_canvas(tk_root: tk.Tk) -> XiangqiCanvas:
    return XiangqiCanvas(tk_root, cell=40, margin=34)


class TestGeometry:
    def test_canvas_is_9x10(self, tk_root: tk.Tk) -> None:
        """宽 9 列、高 10 行（非正方形棋盘）。"""
        canvas = make_canvas(tk_root)
        assert int(canvas["width"]) == 34 * 2 + 40 * 8
        assert int(canvas["height"]) == 34 * 2 + 40 * 9

    def test_pixel_to_grid_maps_centers(self, tk_root: tk.Tk) -> None:
        canvas = make_canvas(tk_root)
        assert canvas.pixel_to_grid(34 + 3 * 40, 34 + 5 * 40) == Move(5, 3)
        assert canvas.pixel_to_grid(34, 34) == Move(0, 0)
        assert canvas.pixel_to_grid(34 + 8 * 40, 34 + 9 * 40) == Move(9, 8)

    def test_pixel_to_grid_rejects_out_of_range(self, tk_root: tk.Tk) -> None:
        canvas = make_canvas(tk_root)
        assert canvas.pixel_to_grid(0, 0) is None
        assert canvas.pixel_to_grid(999, 999) is None
        # 画布内但超出首行（顶边距区间）
        assert canvas.pixel_to_grid(34 + 3 * 40, 10) is None


class TestBoardGeometry:
    """棋盘底的坐标几何（防 x/y 解包错位这类整体坍缩回归）。"""

    def _lines(self, canvas: XiangqiCanvas) -> list[list[float]]:
        return [canvas.coords(i) for i in canvas.find_all() if canvas.type(i) == "line"]

    def _texts(self, canvas: XiangqiCanvas) -> dict[str, list[float]]:
        return {
            canvas.itemcget(i, "text"): canvas.coords(i)
            for i in canvas.find_all()
            if canvas.type(i) == "text"
        }

    def test_side_verticals_span_full_height(self, tk_root: tk.Tk) -> None:
        """两侧边线从第一行贯穿到最后一行（曾因取错轴坍缩成点）。"""
        canvas = make_canvas(tk_root)
        lines = self._lines(canvas)
        assert [34.0, 34.0, 34.0, 394.0] in lines  # col 0
        assert [354.0, 34.0, 354.0, 394.0] in lines  # col 8

    def test_middle_verticals_break_at_river(self, tk_root: tk.Tk) -> None:
        """中间列纵线在楚河汉界断开：上段到第 4 行、下段从第 5 行起。"""
        canvas = make_canvas(tk_root)
        lines = self._lines(canvas)
        x = 34 + 4 * 40  # col 4
        assert [x, 34.0, x, 194.0] in lines  # 上段
        assert [x, 234.0, x, 394.0] in lines  # 下段

    def test_all_lines_within_board_bounds(self, tk_root: tk.Tk) -> None:
        """所有线段（网格/斜线/折角）都落在棋盘纵向范围内。"""
        canvas = make_canvas(tk_root)
        for line in self._lines(canvas):
            assert min(line[1], line[3]) >= 30, line  # 上界（允许折角略靠近边）
            assert max(line[1], line[3]) <= 398, line  # 下界

    def test_outer_border_rectangle(self, tk_root: tk.Tk) -> None:
        canvas = make_canvas(tk_root)
        rects = [canvas.coords(i) for i in canvas.find_all() if canvas.type(i) == "rectangle"]
        assert [31.0, 31.0, 357.0, 397.0] in rects

    def test_river_text_centered_between_ranks(self, tk_root: tk.Tk) -> None:
        """楚河/汉界题在河界正中（第 4、5 行之间）。"""
        texts = self._texts(make_canvas(tk_root))
        assert texts["楚 河"] == [114.0, 214.0]  # col 2，河界中线
        assert texts["汉 界"] == [274.0, 214.0]  # col 6

    def test_file_labels_top_black_bottom_red(self, tk_root: tk.Tk) -> None:
        """顶部黑方数字、底部红方汉字（红方从己方右侧数：col 0 = 九）。"""
        texts = self._texts(make_canvas(tk_root))
        assert texts["1"] == [34.0, 17.0]  # 顶部第一列
        assert texts["九"] == [34.0, 411.0]  # 底部第一列
        assert texts["一"] == [354.0, 411.0]  # 底部最右列

    def test_board_centers_when_canvas_larger(self, tk_root: tk.Tk) -> None:
        """画布大于棋盘时整盘按偏移居中重画，点击映射同步偏移。"""
        canvas = make_canvas(tk_root)
        canvas.sync_board(XiangqiBoard())  # 有棋子的快照，重放应保留 32 子
        canvas._on_configure(SimpleNamespace(width=800, height=600))
        ox = (800 - 388) // 2
        oy = (600 - 428) // 2
        lines = self._lines(canvas)
        assert [34 + ox, 34 + oy, 34 + ox, 394 + oy] in lines  # col 0 全高
        assert len(canvas.find_withtag(PIECE_TAG)) == 64  # 棋子随重放恢复
        assert canvas.pixel_to_grid(34 + ox, 34 + oy) == Move(0, 0)

    def test_no_offset_when_canvas_fits_board(self, tk_root: tk.Tk) -> None:
        """画布恰好等于棋盘尺寸（默认请求宽高）时偏移为零。"""
        canvas = make_canvas(tk_root)
        canvas._on_configure(SimpleNamespace(width=388, height=428))
        assert (canvas._offset_x, canvas._offset_y) == (0, 0)


class TestSyncBoard:
    def test_initial_position_draws_32_pieces(self, tk_root: tk.Tk) -> None:
        """起始局面 32 子，每子 = 圆片 + 汉字两个 item。"""
        canvas = make_canvas(tk_root)
        canvas.sync_board(XiangqiBoard())
        assert len(canvas.find_withtag(PIECE_TAG)) == 64

    def test_piece_font_fits_inside_inner_circle(self, tk_root: tk.Tk) -> None:
        """棋字外接矩形的四角不超出内圈（字号用像素单位，避免 DPI 放大）。"""
        canvas = make_canvas(tk_root)  # cell=40
        family, size, weight = canvas._piece_font
        assert size < 0  # 负数字号 = 像素
        font = tkfont.Font(family=family, size=size, weight=weight)
        half_w = max(font.measure(ch) for ch in "帅将士象马车炮卒仕相兵") / 2
        half_h = font.metrics("ascent") / 2  # 汉字占高；linespace 含空降部
        half_diagonal = (half_w**2 + half_h**2) ** 0.5
        inner_radius = 40 * 0.44 * 0.78 * 0.94
        assert half_diagonal <= inner_radius
        # 也不能为了保险缩得过小：应接近内圈可用上限
        assert size <= -14

    def test_last_move_marks_origin_and_destination(self, tk_root: tk.Tk) -> None:
        board = XiangqiBoard()
        board.place(Move(*H2E2), color=1)
        canvas = make_canvas(tk_root)
        canvas.sync_board(board, last_move=board.last_move()[0])
        assert len(canvas.find_withtag(LAST_TAG)) == 2

    def test_sync_without_last_move_draws_no_mark(self, tk_root: tk.Tk) -> None:
        board = XiangqiBoard()
        board.place(Move(*H2E2), color=1)
        canvas = make_canvas(tk_root)
        canvas.sync_board(board)
        assert len(canvas.find_withtag(LAST_TAG)) == 0


class TestSelectionAndHint:
    def test_show_selection_draws_ring_and_targets(self, tk_root: tk.Tk) -> None:
        """选中光环 1 个 + 每个合法落点 1 个标记。"""
        board = XiangqiBoard()
        targets = rules.legal_targets(board.grid, 7, 7)  # 红炮（h2）
        assert targets  # 起始局面红炮必有落点
        canvas = make_canvas(tk_root)
        canvas.sync_board(board)
        canvas.show_selection(Move(7, 7), targets)
        assert len(canvas.find_withtag(SELECT_TAG)) == 1 + len(targets)

    def test_clear_selection(self, tk_root: tk.Tk) -> None:
        board = XiangqiBoard()
        canvas = make_canvas(tk_root)
        canvas.sync_board(board)
        canvas.show_selection(Move(7, 7), rules.legal_targets(board.grid, 7, 7))
        canvas.clear_selection()
        assert len(canvas.find_withtag(SELECT_TAG)) == 0

    def test_show_hint_marks_start_and_end(self, tk_root: tk.Tk) -> None:
        canvas = make_canvas(tk_root)
        canvas.sync_board(XiangqiBoard())
        canvas.show_hint(Move(*H2E2), 1)
        assert len(canvas.find_withtag(HINT_TAG)) == 2

    def test_show_pending_draws_virtual_piece(self, tk_root: tk.Tk) -> None:
        """预选落点画虚拟棋子：圆片 + 内圈 + 汉字，等待二次点击确认。"""
        canvas = make_canvas(tk_root)
        canvas.sync_board(XiangqiBoard())
        assert canvas.pending_move is None
        canvas.show_pending(Move(*H2E2))
        assert canvas.pending_move == Move(*H2E2)
        assert len(canvas.find_withtag(PENDING_TAG)) == 3

    def test_pending_capture_adds_capture_ring(self, tk_root: tk.Tk) -> None:
        """预选吃子时虚拟棋子外再套红环，提示这步会吃子。"""
        board = XiangqiBoard("4k4/9/9/9/4p4/4R4/9/9/9/3K5 w - - 0 1")
        canvas = make_canvas(tk_root)
        canvas.sync_board(board)
        canvas.show_pending(Move(5, 4, 4, 4))
        outlines = {
            canvas.itemcget(i, "outline")
            for i in canvas.find_withtag(PENDING_TAG)
            if canvas.type(i) == "oval"
        }
        assert theme.CAPTURE_RING in outlines

    def test_clear_pending_and_selection(self, tk_root: tk.Tk) -> None:
        board = XiangqiBoard()
        canvas = make_canvas(tk_root)
        canvas.sync_board(board)
        canvas.show_selection(Move(7, 7), rules.legal_targets(board.grid, 7, 7))
        canvas.show_pending(Move(*H2E2))
        assert canvas.pending_move is not None
        canvas.clear_pending()
        assert canvas.pending_move is None
        assert len(canvas.find_withtag(SELECT_TAG)) > 0  # 只取消虚拟棋子，选子保留

        canvas.show_pending(Move(*H2E2))
        canvas.clear_selection()
        assert canvas.pending_move is None
        assert len(canvas.find_withtag(PENDING_TAG)) == 0

    def test_sync_board_clears_pending(self, tk_root: tk.Tk) -> None:
        canvas = make_canvas(tk_root)
        canvas.sync_board(XiangqiBoard())
        canvas.show_pending(Move(*H2E2))
        canvas.sync_board(XiangqiBoard())
        assert canvas.pending_move is None
        assert len(canvas.find_withtag(PENDING_TAG)) == 0

    def test_capture_target_uses_capture_color(self, tk_root: tk.Tk) -> None:
        """可吃子的落点用红环，与空位绿点区分。"""
        board = XiangqiBoard("4k4/9/9/9/4p4/4R4/9/9/9/3K5 w - - 0 1")
        targets = rules.legal_targets(board.grid, 5, 4)
        assert (4, 4) in targets  # 车可吃卒
        canvas = make_canvas(tk_root)
        canvas.sync_board(board)
        canvas.show_selection(Move(5, 4), targets)
        outlines = {
            canvas.itemcget(i, "outline")
            for i in canvas.find_withtag(SELECT_TAG)
            if canvas.type(i) == "oval"
        }
        assert theme.CAPTURE_RING in outlines

    def test_check_ring_show_and_clear(self, tk_root: tk.Tk) -> None:
        canvas = make_canvas(tk_root)
        canvas.sync_board(XiangqiBoard())
        canvas.show_check((0, 4))  # 黑将
        assert len(canvas.find_withtag(CHECK_TAG)) == 1
        canvas.clear_check()
        assert len(canvas.find_withtag(CHECK_TAG)) == 0

    def test_overlays_survive_configure_replay(self, tk_root: tk.Tk) -> None:
        """画布尺寸变化整盘重放时，选子/建议/将军/终局覆盖层不应丢失。"""
        board = XiangqiBoard()
        canvas = make_canvas(tk_root)
        canvas.sync_board(board)
        targets = rules.legal_targets(board.grid, 7, 7)
        canvas.show_selection(Move(7, 7), targets)
        canvas.show_pending(Move(*H2E2))
        canvas.show_hint(Move(*H2E2), 1)
        canvas.show_check((0, 4))
        canvas.highlight_win([Move(0, 4)])

        canvas._on_configure(SimpleNamespace(width=800, height=600))

        assert len(canvas.find_withtag(SELECT_TAG)) == 1 + len(targets)
        assert len(canvas.find_withtag(PENDING_TAG)) == 3
        assert len(canvas.find_withtag(HINT_TAG)) == 2
        assert len(canvas.find_withtag(CHECK_TAG)) == 1
        assert len(canvas.find_withtag(WIN_TAG)) == 1


class TestFlippedBoard:
    """执黑时棋盘旋转 180°：黑方在下方，坐标与纵线号同步翻转。"""

    def make_flipped(self, tk_root: tk.Tk) -> XiangqiCanvas:
        return XiangqiCanvas(tk_root, cell=40, margin=34, flipped=True)

    def _texts(self, canvas: XiangqiCanvas) -> dict[str, list[float]]:
        return {
            canvas.itemcget(i, "text"): canvas.coords(i)
            for i in canvas.find_all()
            if canvas.type(i) == "text"
        }

    def test_black_pieces_at_bottom(self, tk_root: tk.Tk) -> None:
        canvas = self.make_flipped(tk_root)
        canvas.sync_board(XiangqiBoard())
        texts = self._texts(canvas)
        assert texts["将"][1] > texts["帅"][1]  # 黑将在下方，红帅在上方

    def test_pixel_to_grid_rotates(self, tk_root: tk.Tk) -> None:
        canvas = self.make_flipped(tk_root)
        # 屏幕左上角 = 逻辑右下角（9,8），屏幕下方中路 = 黑将（0,4）
        assert canvas.pixel_to_grid(34, 34) == Move(9, 8)
        assert canvas.pixel_to_grid(34 + 8 * 40, 34 + 9 * 40) == Move(0, 0)
        assert canvas.pixel_to_grid(34 + 4 * 40, 34 + 9 * 40) == Move(0, 4)

    def test_file_labels_follow_orientation(self, tk_root: tk.Tk) -> None:
        texts = self._texts(self.make_flipped(tk_root))
        assert texts["一"] == [34.0, 17.0]  # 顶部红方：左起 一
        assert texts["9"] == [34.0, 411.0]  # 底部黑方：左起 9

    def test_set_flipped_redraws_pieces(self, tk_root: tk.Tk) -> None:
        canvas = make_canvas(tk_root)
        canvas.sync_board(XiangqiBoard())
        assert self._texts(canvas)["将"][1] < self._texts(canvas)["帅"][1]
        canvas.set_flipped(True)
        texts = self._texts(canvas)
        assert texts["将"][1] > texts["帅"][1]
        assert len(canvas.find_withtag(PIECE_TAG)) == 64


class TestEndgame:
    def test_highlight_win_draws_rings(self, tk_root: tk.Tk) -> None:
        canvas = make_canvas(tk_root)
        canvas.sync_board(XiangqiBoard())
        canvas.highlight_win([Move(0, 4)])  # 黑将
        assert len(canvas.find_withtag(WIN_TAG)) == 1
