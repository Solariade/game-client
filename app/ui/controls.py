"""设置区控件：LabelFrame「设置」内的 3×2 宫格与底部右侧「重新开局」按钮。

第一行 3 格（棋种/模型/难度），第二行 2 格（执黑/落棋建议），
右上角第 6 格留空。
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
SUGGESTION_ON = "开"
SUGGESTION_OFF = "关"


class ControlsPanel(ttk.LabelFrame):
    """设置区：棋种、模型、难度、执黑、落棋建议 五格（3×2）；重新开局按钮靠右。"""

    def __init__(
        self,
        master: Any,
        model_names: list[tuple[str, str]],
        on_model_change: Callable[[str], None],
        on_difficulty_change: Callable[[Difficulty], None],
        on_color_change: Callable[[int], None],
        on_suggestion_change: Callable[[bool], None],
        on_restart: Callable[[], None],
        **kwargs: Any,
    ) -> None:
        super().__init__(master, text="设置", padding=(10, 8), **kwargs)
        self._difficulty_values = [d.value for d in Difficulty]
        self._model_map = {display: name for name, display in model_names}
        self._build(
            model_names,
            on_model_change,
            on_difficulty_change,
            on_color_change,
            on_suggestion_change,
            on_restart,
        )

    def _build(
        self,
        model_names: list[tuple[str, str]],
        on_model_change: Callable[[str], None],
        on_difficulty_change: Callable[[Difficulty], None],
        on_color_change: Callable[[int], None],
        on_suggestion_change: Callable[[bool], None],
        on_restart: Callable[[], None],
    ) -> None:
        for col in range(3):
            self.columnconfigure(col, weight=1)

        # 第一行 3 格
        self._game_var, game_box = self._cell(0, 0, "棋种", ["五子棋"])
        game_box.configure(state="disabled")  # 首版仅五子棋，仅展示

        self._model_var, model_box = self._cell(
            0, 1, "模型", [display for _n, display in model_names]
        )
        model_box.bind("<<ComboboxSelected>>", lambda _e: on_model_change(self.current_model))

        self._difficulty_var, diff_box = self._cell(0, 2, "难度", self._difficulty_values)
        self._difficulty_var.set(DEFAULT_DIFFICULTY.value)
        diff_box.bind(
            "<<ComboboxSelected>>", lambda _e: on_difficulty_change(self.current_difficulty)
        )

        # 第二行 2 格，第 3 格留空
        self._color_var, color_box = self._cell(1, 0, "执黑", [USER_BLACK, AI_BLACK])
        color_box.bind("<<ComboboxSelected>>", lambda _e: on_color_change(self.current_user_color))

        self._suggestion_var, suggestion_box = self._cell(
            1, 1, "落棋建议", [SUGGESTION_ON, SUGGESTION_OFF]
        )
        suggestion_box.bind(
            "<<ComboboxSelected>>",
            lambda _e: on_suggestion_change(self.suggestion_enabled),
        )

        restart = ttk.Button(self, text="重新开局", command=on_restart)
        restart.grid(row=2, column=0, columnspan=3, sticky="e", pady=(8, 0))

    def _cell(
        self, row: int, col: int, title: str, values: list[str]
    ) -> tuple[tk.StringVar, ttk.Combobox]:
        """一个设置格：上标签、上下拉。"""
        frame = ttk.Frame(self)
        frame.grid(row=row, column=col, sticky="nsew", padx=(0, 10), pady=(2, 4))
        ttk.Label(frame, text=title, font=theme.FONT_SMALL, foreground=theme.MUTED).pack(anchor="w")
        var = tk.StringVar(value=values[0] if values else "")
        box = ttk.Combobox(
            frame, textvariable=var, values=values, state="readonly", font=theme.FONT_NORMAL
        )
        box.pack(fill="x", pady=(1, 0))
        return var, box

    # ---- 当前选择 ----

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
        """1 = 用户执黑，-1 = AI 执黑。"""
        return 1 if self._color_var.get() == USER_BLACK else -1

    @property
    def suggestion_enabled(self) -> bool:
        """是否显示本地落子建议（默认「开」）。"""
        return self._suggestion_var.get() == SUGGESTION_ON

    def set_user_color(self, color: int) -> None:
        """程序化设置执黑下拉（如 AI 思考期间回退选择）。"""
        self._color_var.set(USER_BLACK if color == 1 else AI_BLACK)
