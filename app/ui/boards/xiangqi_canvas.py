"""象棋棋盘画布：木色棋盘、九宫斜线、楚河汉界、圆形棋子与选子交互渲染。

本类只负责「画」，不持有对局状态：棋子随 sync_board(board) 整盘重绘，
选子与预选落点状态由 MainWindow 维护，经 show_selection / show_pending 控制。
画布大于棋盘时棋盘自动居中（<Configure> 触发整盘重放）。
"""

from __future__ import annotations

import tkinter.font as tkfont
from collections.abc import Callable
from typing import Any

from app.core.base_game import Move
from app.core.xiangqi import rules
from app.core.xiangqi.board import PIECE_CN, XiangqiBoard
from app.ui import theme
from app.ui.boards.base_board_canvas import BaseBoardCanvas

# 纵线号标注：红方从己方右侧数一~九（col 0 = 九线），黑方从己方右侧数 1~9
_RED_FILES = "九八七六五四三二一"

_PIECE_FAMILY = "Microsoft YaHei UI"
# 覆盖面最广的棋子汉字（用于量取最大字宽）
_PIECE_GLYPHS = "帅将士象马车炮卒仕相兵"

PIECE_TAG = "xq_piece"  # 棋子（圆片 + 汉字）
LAST_TAG = "xq_last"  # 最后一手起点/终点标记
SELECT_TAG = "xq_select"  # 选子光环 + 合法落点
PENDING_TAG = "xq_pending"  # 用户预选、等待二次点击确认的虚拟棋子
HINT_TAG = "xq_hint"  # 建议起点/终点标记
CHECK_TAG = "xq_check"  # 被将军的将/帅光环
WIN_TAG = "xq_win"  # 终局高亮（输方将/帅）

# 炮位与兵位折角标记
_MARK_POINTS = tuple(
    [(2, 1), (2, 7), (7, 1), (7, 7)]
    + [(3, c) for c in range(0, 9, 2)]
    + [(6, c) for c in range(0, 9, 2)]
)


class XiangqiCanvas(BaseBoardCanvas):
    """9 列 × 10 行象棋棋盘。

    逻辑坐标 row 0 为黑方底线、row 9 为红方底线；默认红方在屏幕下方，
    ``flipped=True`` 时旋转 180°（执黑视角），黑方位于屏幕下方。
    """

    def __init__(
        self,
        master: Any,
        cell: int = 46,
        margin: int = 56,
        on_click: Callable[[Move], None] | None = None,
        flipped: bool = False,
        **kwargs: Any,
    ) -> None:
        super().__init__(
            master,
            rules.COLS,
            cell,
            margin,
            on_click,
            rows=rules.ROWS,
            bg=theme.BOARD_BG,
            **kwargs,
        )
        self._grid = [[""] * rules.COLS for _ in range(rules.ROWS)]
        # 翻转 180°：用户执黑时让黑方在下方，己方棋子总在自己面前
        self._flipped = flipped
        self._last_move: Move | None = None
        # 覆盖层状态：<Configure> 重放时按这些字段恢复，避免选子/建议/将军标记消失
        self._selection: Move | None = None
        self._selection_targets: list[tuple[int, int]] = []
        self._pending: Move | None = None
        self._hint_move: Move | None = None
        self._check_king: tuple[int, int] | None = None
        self._win_cells: list[Move] = []
        self._offset_x = 0  # 画布大于棋盘时的居中偏移（随 <Configure> 更新）
        self._offset_y = 0
        self._piece_font = self._fit_piece_font(cell)
        self._river_font = ("Microsoft YaHei UI", int(cell * 0.42), "bold")
        self.bind("<Configure>", self._on_configure)
        self.draw()

    @staticmethod
    def _fit_piece_font(cell: int) -> tuple[str, int, str]:
        """选一个不超出棋子内圈的像素字号（负数字号 = 像素，避免 DPI 放大）。

        内圈半径 = cell × 0.44 × 0.78。用字宽与 ascent（汉字实际占高，
        linespace 含空降部，会把字号压得过小）构成外接矩形，要求四角都在
        内圈内并留 6% 余量，避免视觉上压到描边。
        """
        inner_radius = cell * 0.44 * 0.78 * 0.94
        for px in range(int(inner_radius * 2), 7, -1):
            font = tkfont.Font(family=_PIECE_FAMILY, size=-px, weight="bold")
            half_w = max(font.measure(ch) for ch in _PIECE_GLYPHS) / 2
            half_h = int(font.metrics("ascent")) / 2
            if (half_w**2 + half_h**2) ** 0.5 <= inner_radius:
                return (_PIECE_FAMILY, -px, "bold")
        return (_PIECE_FAMILY, -8, "bold")

    # ---- 坐标换算 ----

    def _screen_xy(self, row: int, col: int) -> tuple[int, int]:
        """屏幕行/列 → 像素坐标（不做翻转）。"""
        return (
            self.margin + self._offset_x + col * self.cell,
            self.margin + self._offset_y + row * self.cell,
        )

    def _grid_xy(self, row: int, col: int) -> tuple[int, int]:
        """逻辑坐标（row 0 = 黑方底线）→ 屏幕像素；翻转时旋转 180°。"""
        if self._flipped:
            row, col = rules.ROWS - 1 - row, rules.COLS - 1 - col
        return self._screen_xy(row, col)

    def set_flipped(self, flipped: bool) -> None:
        """切换左右视角（执黑时翻转棋盘），保留当前棋子与覆盖层。"""
        if flipped == self._flipped:
            return
        self._flipped = flipped
        self._paint()

    def _board_pixels(self) -> tuple[int, int]:
        """棋盘本身的像素尺寸（与基类画布请求宽高一致）。"""
        return (
            self.margin * 2 + self.cell * (rules.COLS - 1),
            self.margin * 2 + self.cell * (rules.ROWS - 1),
        )

    def _on_configure(self, event: Any) -> None:
        """画布尺寸变化时把棋盘居中重画（选子/建议标记需重选才会恢复）。"""
        bw, bh = self._board_pixels()
        offset_x = max(0, (event.width - bw) // 2)
        offset_y = max(0, (event.height - bh) // 2)
        if (offset_x, offset_y) != (self._offset_x, self._offset_y):
            self._offset_x, self._offset_y = offset_x, offset_y
            self._paint()

    def pixel_to_grid(self, x: int, y: int) -> Move | None:
        screen_col = round((x - self.margin - self._offset_x) / self.cell)
        screen_row = round((y - self.margin - self._offset_y) / self.cell)
        if not (0 <= screen_col < self.board_size and 0 <= screen_row < self.rows):
            return None
        cx, cy = self._screen_xy(screen_row, screen_col)
        if abs(x - cx) > self.cell / 2 or abs(y - cy) > self.cell / 2:
            return None
        if self._flipped:
            screen_row, screen_col = (
                rules.ROWS - 1 - screen_row,
                rules.COLS - 1 - screen_col,
            )
        return Move(screen_row, screen_col)

    # ---- 棋盘底 ----

    def draw(self) -> None:
        """棋盘底：网格、九宫斜线、炮兵位标记、楚河汉界与纵线号。

        骨架一律用 ``_screen_xy``（屏幕行/列），棋子与覆盖层用 ``_grid_xy``
        （逻辑坐标，随 ``_flipped`` 旋转 180°）。这样翻转棋盘时骨架不参与
        坐标变换，避免 ``_grid_xy(0, 0)`` 在翻转后不再对应左上角。
        """
        self.delete("all")
        left, top = self._screen_xy(0, 0)  # 左上角
        right, _ = self._screen_xy(0, rules.COLS - 1)  # 最右列的 x
        _, bottom = self._screen_xy(rules.ROWS - 1, 0)  # 最底行的 y

        # 横线 10 条全宽
        for r in range(rules.ROWS):
            _, y = self._screen_xy(r, 0)
            self.create_line(left, y, right, y, fill=theme.BOARD_LINE, width=1)
        # 纵线：两侧全高；中间各列在楚河汉界处断开
        _, river_top_y = self._screen_xy(4, 0)
        _, river_bottom_y = self._screen_xy(5, 0)
        for c in range(rules.COLS):
            x, _ = self._screen_xy(0, c)
            if c in (0, rules.COLS - 1):
                self.create_line(x, top, x, bottom, fill=theme.BOARD_LINE, width=1)
            else:
                self.create_line(x, top, x, river_top_y, fill=theme.BOARD_LINE, width=1)
                self.create_line(x, river_bottom_y, x, bottom, fill=theme.BOARD_LINE, width=1)

        # 外框加粗 + 九宫斜线（九宫以中线对称，逻辑/屏幕坐标等价）
        self.create_rectangle(
            left - 3, top - 3, right + 3, bottom + 3, outline=theme.BOARD_LINE, width=3
        )
        for r0, r1, c0, c1 in ((0, 2, 3, 5), (0, 2, 5, 3), (7, 9, 3, 5), (7, 9, 5, 3)):
            x0, y0 = self._grid_xy(r0, c0)
            x1, y1 = self._grid_xy(r1, c1)
            self.create_line(x0, y0, x1, y1, fill=theme.BOARD_LINE, width=1)

        for r, c in _MARK_POINTS:
            self._draw_mark(r, c)

        # 楚河汉界：河界正中题字（位置固定在屏幕左/右）
        river_y = (river_top_y + river_bottom_y) / 2
        for text, col in (("楚 河", 2), ("汉 界", 6)):
            x, _ = self._screen_xy(0, col)
            self.create_text(x, river_y, text=text, fill=theme.RIVER_TEXT, font=self._river_font)

        # 纵线号：下方永远是当前执子方的一侧。
        # 未翻转：顶部黑 1~9、底部红 九~一；翻转后：顶部红 一~九、底部黑 9~1。
        if self._flipped:
            top_labels = [_RED_FILES[rules.COLS - 1 - c] for c in range(rules.COLS)]
            bottom_labels = [str(rules.COLS - c) for c in range(rules.COLS)]
        else:
            top_labels = [str(c + 1) for c in range(rules.COLS)]
            bottom_labels = list(_RED_FILES)
        for c in range(rules.COLS):
            x, _ = self._screen_xy(0, c)
            self.create_text(
                x,
                top - self.margin * 0.5,
                text=top_labels[c],
                fill=theme.COORD_TEXT,
                font=theme.FONT_SMALL,
            )
            self.create_text(
                x,
                bottom + self.margin * 0.5,
                text=bottom_labels[c],
                fill=theme.COORD_TEXT,
                font=theme.FONT_SMALL,
            )

    def _draw_mark(self, r: int, c: int) -> None:
        """炮位/兵位折角标记（边缘列只画内侧一半）。"""
        x, y = self._grid_xy(r, c)
        gap = self.cell * 0.10
        arm = self.cell * 0.16
        for dx in (-1, 1):
            if c == 0 and dx < 0 or c == rules.COLS - 1 and dx > 0:
                continue
            for dy in (-1, 1):
                sx, sy = x + dx * gap, y + dy * gap
                self.create_line(sx, sy, sx, sy + dy * arm, fill=theme.BOARD_LINE, width=1)
                self.create_line(sx, sy, sx + dx * arm, sy, fill=theme.BOARD_LINE, width=1)

    # ---- 棋子 ----

    def draw_stone(self, move: Move, color: int, is_last: bool = False) -> None:
        """基类契约实现：按最近一次 sync_board 的快照绘制该处棋子。"""
        piece = self._grid[move.row][move.col]
        if piece:
            self._draw_piece(move.row, move.col, piece)

    def _draw_piece(self, r: int, c: int, piece: str) -> None:
        x, y = self._grid_xy(r, c)
        radius = self.cell * 0.44
        color = theme.RED_PIECE if piece.isupper() else theme.BLACK_PIECE
        self.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            fill=theme.PIECE_BG,
            outline=color,
            width=2,
            tags=(PIECE_TAG,),
        )
        # 内圈细线（传统棋子样式）；不挂 PIECE_TAG，保持「每子两个 item」的约定
        inner = radius * 0.78
        self.create_oval(x - inner, y - inner, x + inner, y + inner, outline=color, width=1)
        self.create_text(
            x, y, text=PIECE_CN[piece], fill=color, font=self._piece_font, tags=(PIECE_TAG,)
        )

    def sync_board(self, board: XiangqiBoard, last_move: Move | None = None) -> None:
        """整盘重绘；last_move 标出起点小圈与终点光环。

        覆盖层（选子/建议/将军/终局）随局面变化作废，由 MainWindow 重新绘制。
        """
        self._grid = [row[:] for row in board.grid]
        self._last_move = last_move
        self._selection = None
        self._selection_targets = []
        self._pending = None
        self._hint_move = None
        self._check_king = None
        self._win_cells = []
        self._paint()

    def _paint(self) -> None:
        """按当前快照与居中偏移画全部内容（sync 与尺寸变化重放共用）。"""
        self.draw()
        for r in range(rules.ROWS):
            for c in range(rules.COLS):
                if self._grid[r][c]:
                    self._draw_piece(r, c, self._grid[r][c])
        self._draw_last_move()
        self._draw_selection()
        self._draw_pending()
        self._draw_hint()
        self._draw_check()
        self._draw_win()

    def _draw_last_move(self) -> None:
        last_move = self._last_move
        if last_move is None or last_move.to_row is None or last_move.to_col is None:
            return
        x, y = self._grid_xy(last_move.row, last_move.col)
        r0 = self.cell * 0.12
        self.create_oval(
            x - r0,
            y - r0,
            x + r0,
            y + r0,
            outline=theme.LAST_MOVE_MARK,
            width=2,
            tags=(LAST_TAG,),
        )
        x, y = self._grid_xy(last_move.to_row, last_move.to_col)
        r1 = self.cell * 0.52
        self.create_oval(
            x - r1,
            y - r1,
            x + r1,
            y + r1,
            outline=theme.LAST_MOVE_MARK,
            width=2,
            tags=(LAST_TAG,),
        )

    # ---- 选子与建议（状态由 MainWindow 驱动，画布缓存一份用于尺寸变化重放） ----

    def show_selection(self, move: Move, targets: list[tuple[int, int]]) -> None:
        """选中棋子光环（蓝）+ 合法落点（空位绿点、可吃敌子红环）。"""
        self.clear_selection()
        self._selection = move
        self._selection_targets = list(targets)
        self._draw_selection()

    def _draw_selection(self) -> None:
        move = self._selection
        if move is None:
            return
        x, y = self._grid_xy(move.row, move.col)
        radius = self.cell * 0.52
        self.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            outline=theme.SELECT_RING,
            width=3,
            tags=(SELECT_TAG,),
        )
        for tr, tc in self._selection_targets:
            ring = theme.CAPTURE_RING if self._grid[tr][tc] else theme.HINT_RING
            self._draw_target(tr, tc, SELECT_TAG, self.cell * 0.11, ring_color=ring)

    def clear_selection(self) -> None:
        self._selection = None
        self._selection_targets = []
        self.clear_pending()  # 取消选子/落子后虚拟棋子一并移除
        self.delete(SELECT_TAG)

    # ---- 预选落子（虚拟棋子，二次点击确认） ----

    def show_pending(self, move: Move) -> None:
        """在 move 的终点画虚拟棋子，等待用户再次点击确认落子。

        视觉：与真实棋子等大的实心圆片（底色同棋子）+ 棋子色虚线外环 +
        汉字，既盖住原位置的敌子，又能一眼看出是待确认的虚拟棋子；
        若为吃子，外圈再套一圈红环提示。
        """
        if move.to_row is None or move.to_col is None:
            return
        self.clear_pending()
        self._pending = move
        self._draw_pending()

    def _draw_pending(self) -> None:
        move = self._pending
        if move is None or move.to_row is None or move.to_col is None:
            return
        r, c = move.to_row, move.to_col
        piece = self._grid[move.row][move.col]
        if not piece:
            return
        x, y = self._grid_xy(r, c)
        color = theme.RED_PIECE if piece.isupper() else theme.BLACK_PIECE
        radius = self.cell * 0.42
        self.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            fill=theme.PIECE_BG,
            outline=color,
            width=3,
            dash=(5, 3),
            tags=(PENDING_TAG,),
        )
        inner = radius * 0.78
        self.create_oval(
            x - inner, y - inner, x + inner, y + inner, outline=color, width=1, tags=(PENDING_TAG,)
        )
        self.create_text(
            x, y, text=PIECE_CN[piece], fill=color, font=self._piece_font, tags=(PENDING_TAG,)
        )
        if self._grid[r][c]:  # 吃子：外圈红环，与选子时的可吃标记呼应
            capture = self.cell * 0.56
            self.create_oval(
                x - capture,
                y - capture,
                x + capture,
                y + capture,
                outline=theme.CAPTURE_RING,
                width=2,
                tags=(PENDING_TAG,),
            )

    def clear_pending(self) -> None:
        self._pending = None
        self.delete(PENDING_TAG)

    def show_hint(self, move: Move, color: int) -> None:
        """本地建议：起点虚线环 + 终点标记（color 参数为接口兼容保留）。"""
        self.clear_hint()
        if move.to_row is None or move.to_col is None:
            return
        self._hint_move = move
        self._draw_hint()

    def _draw_hint(self) -> None:
        move = self._hint_move
        if move is None or move.to_row is None or move.to_col is None:
            return
        x, y = self._grid_xy(move.row, move.col)
        radius = self.cell * 0.52
        self.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            outline=theme.HINT_RING,
            width=2,
            dash=(4, 3),
            tags=(HINT_TAG,),
        )
        self._draw_target(move.to_row, move.to_col, HINT_TAG, self.cell * 0.12)

    def clear_hint(self) -> None:
        self._hint_move = None
        self.delete(HINT_TAG)

    def _draw_target(
        self, tr: int, tc: int, tag: str, dot_radius: float, *, ring_color: str = theme.HINT_RING
    ) -> None:
        """落点标记：空位画实心点，有敌子画环（套在棋子外）。"""
        x, y = self._grid_xy(tr, tc)
        if self._grid[tr][tc]:
            radius = self.cell * 0.52
            self.create_oval(
                x - radius,
                y - radius,
                x + radius,
                y + radius,
                outline=ring_color,
                width=2,
                tags=(tag,),
            )
        else:
            self.create_oval(
                x - dot_radius,
                y - dot_radius,
                x + dot_radius,
                y + dot_radius,
                fill=ring_color,
                outline="",
                tags=(tag,),
            )

    def show_check(self, cell: tuple[int, int]) -> None:
        """被将军一方的将/帅加红色警示环。"""
        self.clear_check()
        self._check_king = cell
        self._draw_check()

    def _draw_check(self) -> None:
        if self._check_king is None:
            return
        r, c = self._check_king
        x, y = self._grid_xy(r, c)
        radius = self.cell * 0.58
        self.create_oval(
            x - radius,
            y - radius,
            x + radius,
            y + radius,
            outline=theme.CHECK_RING,
            width=3,
            tags=(CHECK_TAG,),
        )

    def clear_check(self) -> None:
        self._check_king = None
        self.delete(CHECK_TAG)

    def highlight_win(self, cells: list[Move]) -> None:
        """终局高亮（象棋用于输方将/帅）。"""
        self._win_cells = list(cells)
        self.delete(WIN_TAG)
        self._draw_win()

    def _draw_win(self) -> None:
        for move in self._win_cells:
            x, y = self._grid_xy(move.row, move.col)
            radius = self.cell * 0.56
            self.create_oval(
                x - radius,
                y - radius,
                x + radius,
                y + radius,
                outline=theme.WIN_LINE,
                width=3,
                tags=(WIN_TAG,),
            )

    @property
    def pending_move(self) -> Move | None:
        """当前预选、等待二次点击确认的着法（含起点与终点）。"""
        return self._pending
