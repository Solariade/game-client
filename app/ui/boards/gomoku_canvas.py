"""五子棋棋盘绘制与点击。

首版无背景图：Canvas 绘制木色底 + 15×15 网格 + 五个星位 + 坐标（A~O / 1~15）。
预留 self._bg_img：后续放入 assets/images/board_bg.png 后仅需改 _draw_background。
"""

from __future__ import annotations

import tkinter as tk
from typing import Any

from app.common.paths import asset
from app.core.base_game import Move
from app.core.constants import EMPTY
from app.core.gomoku.board import GomokuBoard
from app.ui import theme
from app.ui.boards.base_board_canvas import BaseBoardCanvas

STAR_POINTS = ((3, 3), (3, 11), (11, 3), (11, 11), (7, 7))
HINT_TAG = "hint"  # 引擎建议落子的虚拟棋子
PREVIEW_TAG = "preview"  # 用户第一次点击产生的待确认虚拟棋子


class GomokuCanvas(BaseBoardCanvas):
    """五子棋棋盘画布。"""

    def __init__(
        self,
        master: Any,
        board_size: int = 15,
        cell: int = 34,
        margin: int = 30,
        on_click: Any = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, board_size, cell, margin, on_click, bg=theme.BOARD_BG, **kwargs)
        self._bg_img: tk.PhotoImage | None = None  # 预留背景图引用防 GC
        self._hint: Move | None = None  # 引擎建议落子位置（虚线虚拟棋子）
        self._pending: Move | None = None  # 用户预选、等待二次点击确认的位置
        self.draw()

    # ---- 绘制 ----

    def draw(self) -> None:
        """绘制整块棋盘底（背景 + 网格 + 星位 + 坐标）。"""
        self.delete("all")
        self._draw_background()
        self._draw_grid()
        self._draw_star_points()
        self._draw_coordinates()

    def _draw_background(self) -> None:
        """木色底；若存在 assets/images/board_bg.png 则改用图片。"""
        bg_path = asset("images", "board_bg.png")
        if bg_path.exists():
            self._bg_img = tk.PhotoImage(file=str(bg_path))
            self.create_image(0, 0, anchor="nw", image=self._bg_img)
        else:
            self._bg_img = None

    def _grid_xy(self, row: int, col: int) -> tuple[float, float]:
        return (
            self.margin + col * self.cell,
            self.margin + row * self.cell,
        )

    def _draw_grid(self) -> None:
        n = self.board_size
        for i in range(n):
            # 横线（第 i 行）：(0,i) → (n-1,i)
            x0, y0 = self._grid_xy(i, 0)
            x1, y1 = self._grid_xy(i, n - 1)
            self.create_line(x0, y0, x1, y1, fill=theme.BOARD_LINE, width=1)
            # 竖线（第 i 列）：(i,0) → (i,n-1)
            x0, y0 = self._grid_xy(0, i)
            x1, y1 = self._grid_xy(n - 1, i)
            self.create_line(x0, y0, x1, y1, fill=theme.BOARD_LINE, width=1)

    def _draw_star_points(self) -> None:
        r = 3
        for row, col in STAR_POINTS:
            x, y = self._grid_xy(row, col)
            self.create_oval(
                x - r, y - r, x + r, y + r, fill=theme.STAR_POINT, outline=theme.STAR_POINT
            )

    def _draw_coordinates(self) -> None:
        """顶部列 A~O，左侧行 1~15。"""
        for col in range(self.board_size):
            x, y = self._grid_xy(0, col)
            self.create_text(
                x,
                y - self.margin / 2 + 4,
                text=chr(ord("A") + col),
                fill=theme.COORD_TEXT,
                font=theme.FONT_SMALL,
            )
        for row in range(self.board_size):
            x, y = self._grid_xy(row, 0)
            self.create_text(
                x - self.margin / 2,
                y,
                text=str(row + 1),
                fill=theme.COORD_TEXT,
                font=theme.FONT_SMALL,
            )

    # ---- 棋子 ----

    def draw_stone(self, move: Move, color: int, is_last: bool = False) -> None:
        """绘制棋子；is_last 时在中心画小红点标记。"""
        if color == EMPTY:
            return
        x, y = self._grid_xy(move.row, move.col)
        r = self.cell * 0.42
        stone_color = theme.BLACK_STONE if color == 1 else theme.WHITE_STONE
        edge_color = theme.BLACK_STONE_EDGE if color == 1 else theme.WHITE_STONE_EDGE
        self.create_oval(
            x - r,
            y - r,
            x + r,
            y + r,
            fill=stone_color,
            outline=edge_color,
            width=1,
        )
        if is_last:
            mark_r = self.cell * 0.10
            self.create_oval(
                x - mark_r,
                y - mark_r,
                x + mark_r,
                y + mark_r,
                fill=theme.LAST_MOVE_MARK,
                outline=theme.LAST_MOVE_MARK,
            )

    def sync_board(self, board: GomokuBoard, last_move: Move | None = None) -> None:
        """按棋盘状态整盘重绘；棋盘已变化，旧的建议与预选同时作废。"""
        self._hint = None
        self._pending = None
        self.draw()
        for move, color in board.history():
            is_last = last_move is not None and move == last_move
            self.draw_stone(move, color, is_last=is_last)

    # ---- 建议落子 / 预选落子（虚拟棋子） ----

    @property
    def hint_move(self) -> Move | None:
        """当前引擎建议落子位置（测试用）。"""
        return self._hint

    @property
    def pending_move(self) -> Move | None:
        """当前用户预选、等待二次点击确认的位置（测试用）。"""
        return self._pending

    def show_hint(self, move: Move, color: int) -> None:
        """画引擎建议落子的虚拟棋子。

        视觉：与真实棋子同大的加粗绿色虚线光环 + 更小的建议棋子
        （黑棋黑色填充、白棋白色填充，均用绿色描边），
        中心不画绿点，也不带角标。
        与用户预选的双圆环虚拟子明确区分。
        """
        self.clear_hint()
        self._hint = move
        x, y = self._grid_xy(move.row, move.col)
        r = self.cell * 0.42
        stone_color = theme.BLACK_STONE if color == 1 else theme.WHITE_STONE

        # 外层绿色虚线光环：尺寸与真实棋子一致，描边加粗
        self.create_oval(
            x - r,
            y - r,
            x + r,
            y + r,
            outline=theme.HINT_RING,
            width=3,
            dash=(4, 3),
            tags=(HINT_TAG,),
        )
        # 缩小的建议棋子：绿色描边，中心不画绿点
        inner_r = r * 0.35
        self.create_oval(
            x - inner_r,
            y - inner_r,
            x + inner_r,
            y + inner_r,
            fill=stone_color,
            outline=theme.HINT_RING,
            width=2,
            tags=(HINT_TAG,),
        )

    def clear_hint(self) -> None:
        """只删除建议虚拟棋子，不影响真实棋子与用户预选。"""
        self._hint = None
        self.delete(HINT_TAG)

    def show_pending(self, move: Move, color: int) -> None:
        """画用户预选的虚拟棋子，等待第二次点击确认落子。

        视觉：内外两个同色圆环 + 中心同色圆点（黑棋黑点、白棋白点）。
        空心设计让网格线透出，和真实棋子、建议虚子都能一眼区分。
        若预选点与建议点重合，先移除建议子，避免两层图形叠在一起。
        """
        self.clear_pending()
        if self._hint == move:
            self.clear_hint()
        self._pending = move
        x, y = self._grid_xy(move.row, move.col)
        r = self.cell * 0.42
        stone_color = theme.BLACK_STONE if color == 1 else theme.WHITE_STONE

        # 外圈
        self.create_oval(
            x - r,
            y - r,
            x + r,
            y + r,
            outline=stone_color,
            width=2,
            tags=(PREVIEW_TAG,),
        )
        # 内圈
        inner_r = r * 0.60
        self.create_oval(
            x - inner_r,
            y - inner_r,
            x + inner_r,
            y + inner_r,
            outline=stone_color,
            width=1,
            tags=(PREVIEW_TAG,),
        )
        # 中心圆点
        dot_r = r * 0.17
        self.create_oval(
            x - dot_r,
            y - dot_r,
            x + dot_r,
            y + dot_r,
            fill=stone_color,
            outline="",
            tags=(PREVIEW_TAG,),
        )

    def clear_pending(self) -> None:
        """只删除用户预选的虚拟棋子，不影响真实棋子与建议子。"""
        self._pending = None
        self.delete(PREVIEW_TAG)

    def highlight_win(self, cells: list[Move]) -> None:
        """高亮获胜五连。"""
        for move in cells:
            x, y = self._grid_xy(move.row, move.col)
            r = self.cell * 0.46
            self.create_oval(
                x - r,
                y - r,
                x + r,
                y + r,
                outline=theme.WIN_LINE,
                width=3,
            )

    # ---- 交互 ----

    def pixel_to_grid(self, x: int, y: int) -> Move | None:
        """像素→最近交叉点；距离过远（> cell/2）或越界返回 None。"""
        col = round((x - self.margin) / self.cell)
        row = round((y - self.margin) / self.cell)
        if not (0 <= row < self.board_size and 0 <= col < self.board_size):
            return None
        px, py = self._grid_xy(row, col)
        if abs(px - x) > self.cell / 2 or abs(py - y) > self.cell / 2:
            return None
        return Move(row, col)
