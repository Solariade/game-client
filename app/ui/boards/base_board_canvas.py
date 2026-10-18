"""棋盘画布抽象基类：定义 draw / pixel_to_grid / on_click 契约。"""

from __future__ import annotations

import tkinter as tk
from abc import ABC, abstractmethod
from collections.abc import Callable
from typing import Any

from app.core.base_game import Move


class BaseBoardCanvas(tk.Canvas, ABC):
    """各棋种棋盘渲染的公共骨架。

    注意：棋盘尺寸属性命名 board_size，避免与 tk.Canvas.size() 方法冲突。
    """

    def __init__(
        self,
        master: Any,
        board_size: int,
        cell: int,
        margin: int,
        on_click: Callable[[Move], None] | None = None,
        **kwargs: Any,
    ) -> None:
        width = margin * 2 + cell * (board_size - 1)
        height = margin * 2 + cell * (board_size - 1)
        super().__init__(master, width=width, height=height, highlightthickness=0, **kwargs)
        self.board_size = board_size
        self.cell = cell
        self.margin = margin
        self.on_click = on_click
        self.bind("<Button-1>", self._handle_click)

    @abstractmethod
    def draw(self) -> None:
        """绘制棋盘底（网格/星位/坐标等）。"""

    @abstractmethod
    def pixel_to_grid(self, x: int, y: int) -> Move | None:
        """像素坐标转棋盘坐标；不合法返回 None。"""

    @abstractmethod
    def draw_stone(self, move: Move, color: int, is_last: bool = False) -> None:
        """在 move 处绘制 color 棋子；is_last 时加标记。"""

    def _handle_click(self, event: Any) -> None:
        move = self.pixel_to_grid(event.x, event.y)
        if move is not None and self.on_click is not None:
            self.on_click(move)
