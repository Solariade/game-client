"""窗口底部状态栏：左侧对局状态，最右落子等待读秒。"""

from __future__ import annotations

import time
import tkinter as tk
from tkinter import ttk
from typing import Any

from app.ui import theme


class StatusBar(ttk.Frame):
    """底部状态栏：上边一条分隔线，正文为左状态、最右读秒。"""

    def __init__(self, master: Any, **kwargs: Any) -> None:
        super().__init__(master, **kwargs)
        ttk.Separator(self, orient="horizontal").pack(side="top", fill="x")

        body = ttk.Frame(self, padding=(10, 4))
        body.pack(fill="x")

        self._status_var = tk.StringVar(value="就绪")
        ttk.Label(body, textvariable=self._status_var, anchor="w", font=theme.FONT_SMALL).pack(
            side="left", fill="x", expand=True
        )

        self._timer_var = tk.StringVar(value="")
        ttk.Label(
            body,
            textvariable=self._timer_var,
            anchor="e",
            font=theme.FONT_SMALL,
            foreground=theme.MUTED,
        ).pack(side="right")

        self._wait_who: str | None = None
        self._wait_verb = "落子"
        self._wait_start = 0.0
        self._after_id: str | None = None

    # ---- 文本属性 ----

    @property
    def text(self) -> str:
        """当前状态文本（测试用）。"""
        return self._status_var.get()

    @property
    def timer_text(self) -> str:
        """读秒文本（测试用）。"""
        return self._timer_var.get()

    def set_status(self, text: str) -> None:
        """更新左侧对局状态。"""
        self._status_var.set(text)

    # ---- 落子等待读秒 ----

    def start_wait(self, who: str, verb: str | None = None) -> None:
        """开始为 who（你 / AI）读秒。

        verb 为动作文案（五子棋「落子」/象棋「行棋」），缺省沿用当前值。
        等待方不变时（如解说结束后仍轮到你）不重置计数；
        切换等待方时从 0 重新计。
        """
        if verb is not None:
            self._wait_verb = verb
        if self._wait_who != who:
            self._wait_who = who
            self._wait_start = time.monotonic()
        self._show_elapsed()
        self._schedule_tick()

    def stop_wait(self) -> None:
        """停止读秒并清空显示（对局结束 / 出错 / 重开）。"""
        self._cancel_tick()
        self._wait_who = None
        self._timer_var.set("")

    def _schedule_tick(self) -> None:
        self._cancel_tick()
        self._after_id = self.after(1000, self._on_tick)

    def _cancel_tick(self) -> None:
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except tk.TclError:  # pragma: no cover - 窗口已销毁
                pass
            self._after_id = None

    def _on_tick(self) -> None:
        self._after_id = None
        if self._wait_who is None:
            return
        self._show_elapsed()
        self._schedule_tick()

    def _show_elapsed(self) -> None:
        if self._wait_who is None:
            return
        seconds = int(time.monotonic() - self._wait_start)
        try:
            self._timer_var.set(f"等待 {self._wait_who} {self._wait_verb} {seconds} 秒")
        except tk.TclError:  # pragma: no cover - 窗口已销毁
            self._cancel_tick()

    def destroy(self) -> None:
        self._cancel_tick()
        super().destroy()
