"""右侧解说面板：流式文本追加、自动滚动、段落有序输出。

有序规则：
- 流式进行中收到的段落头/提示信息先挂起，待流结束后按到达顺序输出，
  避免"对局结束"等文字插进正在流出的解说中间；
- 新一轮开始若上一段解说未完成，由 MainWindow 先作废旧流并 end_stream()
  收束该段，面板内容始终按回合顺序排列。
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Any

from app.ui import theme


class AnalysisPanel(ttk.Frame):
    """AI 分析区域：标题 + 只读 Text 流式输出 + 自动滚动。"""

    def __init__(self, master: Any, **kwargs: Any) -> None:
        super().__init__(master, **kwargs)
        self._streaming = False
        self._pending: list[tuple[str, str]] = []  # ("begin" | "info", text)
        self._build()

    def _build(self) -> None:
        title = ttk.Label(self, text="AI 分析", font=theme.FONT_TITLE)
        title.pack(anchor="w", pady=(0, 6))

        self.text = tk.Text(
            self,
            wrap="word",
            state="disabled",
            height=18,
            font=theme.FONT_COMMENTARY,
            background=theme.PANEL_BG,
            foreground=theme.TEXT,
            relief="flat",
            padx=8,
            pady=8,
        )
        scroll = ttk.Scrollbar(self, orient="vertical", command=self.text.yview)
        self.text.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.text.pack(side="left", fill="both", expand=True)

        self.text.tag_configure("header", foreground=theme.ACCENT, font=theme.FONT_NORMAL)
        self.text.tag_configure("muted", foreground=theme.MUTED, font=theme.FONT_SMALL)

    # ---- 流式接口（主线程调用） ----

    @property
    def streaming(self) -> bool:
        """是否正有一段解说在流出。"""
        return self._streaming

    def begin_turn(self, header: str) -> None:
        """开始一轮解说：空出一行间隔、写段落头并进入流式。"""
        if self._streaming:
            self._pending.append(("begin", header))
            return
        self._begin_block(header)

    def show_header(self, header: str) -> None:
        """写一个段落头（如“第 3 回合”），不开启流式。

        没有选择解说模型时也用它标注回合，保证面板内容始终带回合序号。
        """
        if self._streaming:
            self._pending.append(("begin", header))
            return
        self._begin_block(header)
        self._streaming = False  # 仅标题，不等待后续文本块

    def begin_stream(self) -> None:
        """在已写好的段落头之后开始接收流式文本。"""
        self._streaming = True

    def append_chunk(self, chunk: str) -> None:
        """流式追加一段文本块；无在途流时丢弃。"""
        if not self._streaming:
            return
        self._append(chunk, ())

    def end_stream(self) -> None:
        """结束当前流式段，按到达顺序冲刷挂起的消息。"""
        self._streaming = False
        pending, self._pending = self._pending, []
        for kind, text in pending:
            if kind == "begin":
                self._begin_block(text)
            else:
                self._show_info_now(text)

    def show_info(self, message: str) -> None:
        """显示提示性文字（如等待/结束）；流式进行中先挂起。"""
        if self._streaming:
            self._pending.append(("info", message))
            return
        self._show_info_now(message)

    def clear(self) -> None:
        """清空面板并复位流状态（重开新局用）。"""
        self._streaming = False
        self._pending.clear()
        self.text.configure(state="normal")
        self.text.delete("1.0", "end")
        self.text.configure(state="disabled")

    # ---- 内部 ----

    def _begin_block(self, header: str) -> None:
        if not self._is_empty():
            self._append("\n\n", ())  # 回合之间空一行，形成上下文间隔
        self._append(f"{header}\n", ("header",))
        self._streaming = True

    def _show_info_now(self, message: str) -> None:
        if not self._is_empty():
            self._append("\n", ())
        self._append(f"{message}\n", ("muted",))

    def _is_empty(self) -> bool:
        return self.text.index("end-1c") == "1.0"

    def _append(self, content: str, tags: tuple[str, ...]) -> None:
        self.text.configure(state="normal")
        if tags:
            self.text.insert("end", content, tags)
        else:
            self.text.insert("end", content)
        self.text.see("end")
        self.text.configure(state="disabled")
