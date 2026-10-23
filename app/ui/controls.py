"""设置区控件：LabelFrame「设置」内的 3×2 宫格与底部右侧「重新开局」按钮。

第一行 3 格（棋种/模型/难度），第二行 2 格（执子/落棋建议），
右上角第 6 格留空。棋种下拉仅在传入多个棋种且引擎可用时启用。
"""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import ttk
from typing import Any

from app.ai.difficulty import DEFAULT_DIFFICULTY, Difficulty
from app.ui import theme

USER_BLACK = "我执黑"
AI_BLACK = "AI执黑"
USER_RED = "我执红"
AI_RED = "AI执红"
SUGGESTION_ON = "开"
SUGGESTION_OFF = "关"

# 棋种内部名 → 执子格标签与取值（先手方的执子名，后手方为另一个）
_COLOR_CELLS: dict[str, tuple[str, list[str]]] = {
    "gomoku": ("执黑", [USER_BLACK, AI_BLACK]),
    "xiangqi": ("执红", [USER_RED, AI_RED]),
}


class ControlsPanel(ttk.LabelFrame):
    """设置区：棋种、模型、难度、执子、落棋建议 五格（3×2）；重新开局按钮靠右。"""

    def __init__(
        self,
        master: Any,
        model_names: list[tuple[str, str]],
        on_model_change: Callable[[str], None],
        on_difficulty_change: Callable[[Difficulty], None],
        on_color_change: Callable[[int], None],
        on_suggestion_change: Callable[[bool], None],
        on_restart: Callable[[], None],
        game_options: list[tuple[str, str]] | None = None,
        on_game_change: Callable[[str], None] | None = None,
        on_undo: Callable[[], None] | None = None,
        **kwargs: Any,
    ) -> None:
        super().__init__(master, text="设置", padding=(10, 8), **kwargs)
        self._difficulty_values = [d.value for d in Difficulty]
        self._model_map = {display: name for name, display in model_names}
        self._game_options = game_options or [("gomoku", "五子棋")]
        self._game_map = {display: name for name, display in self._game_options}
        self._undo_button: ttk.Button | None = None
        self._build(
            model_names,
            on_model_change,
            on_difficulty_change,
            on_color_change,
            on_suggestion_change,
            on_restart,
            on_game_change,
            on_undo,
        )

    def _build(
        self,
        model_names: list[tuple[str, str]],
        on_model_change: Callable[[str], None],
        on_difficulty_change: Callable[[Difficulty], None],
        on_color_change: Callable[[int], None],
        on_suggestion_change: Callable[[bool], None],
        on_restart: Callable[[], None],
        on_game_change: Callable[[str], None] | None,
        on_undo: Callable[[], None] | None,
    ) -> None:
        for col in range(3):
            self.columnconfigure(col, weight=1)

        # 第一行 3 格
        self._game_var, self._game_box, _label = self._cell(
            0, 0, "棋种", [display for _n, display in self._game_options]
        )
        if on_game_change is not None and len(self._game_options) > 1:
            self._game_box.bind(
                "<<ComboboxSelected>>", lambda _e: on_game_change(self.current_game)
            )
        else:
            self._game_box.configure(state="disabled")  # 仅一个棋种（或引擎缺失）时只展示

        self._model_var, model_box, _label = self._cell(
            0, 1, "模型", [display for _n, display in model_names]
        )
        model_box.bind("<<ComboboxSelected>>", lambda _e: on_model_change(self.current_model))

        self._difficulty_var, diff_box, _label = self._cell(0, 2, "难度", self._difficulty_values)
        self._difficulty_var.set(DEFAULT_DIFFICULTY.value)
        diff_box.bind(
            "<<ComboboxSelected>>", lambda _e: on_difficulty_change(self.current_difficulty)
        )

        # 第二行 2 格，第 3 格留空
        color_label, color_values = _COLOR_CELLS[self._game_options[0][0]]
        self._color_var, self._color_box, self._color_label = self._cell(
            1, 0, color_label, color_values
        )
        self._color_values = color_values
        self._color_box.bind(
            "<<ComboboxSelected>>", lambda _e: on_color_change(self.current_user_color)
        )

        self._suggestion_var, suggestion_box, _label = self._cell(
            1, 1, "落棋建议", [SUGGESTION_ON, SUGGESTION_OFF]
        )
        suggestion_box.bind(
            "<<ComboboxSelected>>",
            lambda _e: on_suggestion_change(self.suggestion_enabled),
        )

        actions = ttk.Frame(self)
        actions.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(8, 0))
        ttk.Button(actions, text="重新开局", command=on_restart).pack(side="right")
        if on_undo is not None:
            self._undo_button = ttk.Button(actions, text="悔棋", command=on_undo)
            self._undo_button.pack(side="right", padx=(0, 6))

    def _cell(
        self, row: int, col: int, title: str, values: list[str]
    ) -> tuple[tk.StringVar, ttk.Combobox, ttk.Label]:
        """一个设置格：上标签、上下拉。"""
        frame = ttk.Frame(self)
        frame.grid(row=row, column=col, sticky="nsew", padx=(0, 10), pady=(2, 4))
        label = ttk.Label(frame, text=title, font=theme.FONT_SMALL, foreground=theme.MUTED)
        label.pack(anchor="w")
        var = tk.StringVar(value=values[0] if values else "")
        box = ttk.Combobox(
            frame, textvariable=var, values=values, state="readonly", font=theme.FONT_NORMAL
        )
        box.pack(fill="x", pady=(1, 0))
        return var, box, label

    # ---- 当前选择 ----

    @property
    def current_game(self) -> str:
        """棋种内部名（gomoku / xiangqi）。"""
        return self._game_map.get(self._game_var.get(), self._game_options[0][0])

    @property
    def current_model(self) -> str:
        return self._model_map.get(self._model_var.get(), "")

    @property
    def current_difficulty(self) -> Difficulty:
        name = self._difficulty_var.get()
        for d in Difficulty:
            if d.value == name:
                return d
        return DEFAULT_DIFFICULTY

    @property
    def current_user_color(self) -> int:
        """1 = 用户执先手子（五子棋黑 / 象棋红），-1 = AI 先手。"""
        return 1 if self._color_var.get() == self._color_values[0] else -1

    @property
    def suggestion_enabled(self) -> bool:
        """是否显示本地落子建议（默认「开」）。"""
        return self._suggestion_var.get() == SUGGESTION_ON

    def set_user_color(self, color: int) -> None:
        """程序化设置执子下拉（如 AI 思考期间回退选择）。"""
        self._color_var.set(self._color_values[0] if color == 1 else self._color_values[1])

    def set_undo_enabled(self, enabled: bool) -> None:
        """禁用/启用悔棋按钮（AI 思考中、无可悔棋时置灰）。"""
        if self._undo_button is not None:
            self._undo_button.configure(state="normal" if enabled else "disabled")

    def set_game(self, game_type: str) -> None:
        """程序化回退棋种下拉（如切换被拒绝时）。"""
        for name, display in self._game_options:
            if name == game_type:
                self._game_var.set(display)
                return

    def apply_game(self, game_type: str) -> None:
        """棋种切换后更新执子格（标签 + 取值），保持先手选择不变。"""
        color_label, color_values = _COLOR_CELLS.get(game_type, _COLOR_CELLS["gomoku"])
        was_first = self.current_user_color == 1
        self._color_label.configure(text=color_label)
        self._color_box.configure(values=color_values)
        self._color_values = color_values
        self._color_var.set(color_values[0] if was_first else color_values[1])
