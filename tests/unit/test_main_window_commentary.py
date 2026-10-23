"""MainWindow 解说链路冒烟：主线程组装提示词 → 后台流式 → 面板按序显示。

覆盖 M12 参数化后的 UI 胶水（Tk 不可用时自动跳过）。
"""

from __future__ import annotations

import time

from app.core.base_game import Move
from app.services.commentary_service import CommentaryService
from app.services.game_service import GameService, TurnResult
from app.ui.main_window import MainWindow


class StubClient:
    """同步吐两段的假 LLM。"""

    def stream_commentary(self, prompt: str):
        assert "五子棋" in prompt  # 提示词确已组装并送达
        yield "红先布局，"
        yield "稳健。"


class StubRegistry:
    available = ["stub"]

    def display_name(self, name: str) -> str:
        return name

    def get(self, name: str) -> StubClient:
        return StubClient()


def _pump_until(tk_root, predicate, timeout: float = 3.0) -> bool:
    """驱动 Tk 事件循环直到条件成立或超时（poller 经 root.after 派发队列事件）。"""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        tk_root.update()
        if predicate():
            return True
        time.sleep(0.02)
    return False


def test_commentary_streams_to_panel(tk_root) -> None:
    service = GameService(user_color=1)
    service.config.model_name = "stub"
    mw = MainWindow(tk_root, service, CommentaryService(), StubRegistry())

    mw._user_result = TurnResult(move=Move(7, 7), color=1, game_over=False)
    ai_result = TurnResult(move=Move(7, 8), color=-1, game_over=False)
    mw._start_commentary(ai_result)

    assert _pump_until(tk_root, lambda: "稳健。" in mw.panel.text.get("1.0", "end"))
    text = mw.panel.text.get("1.0", "end")
    assert "红先布局，" in text
    assert mw.panel.streaming is False  # 流式段已收束
    assert mw._comment_seq >= 1


def test_commentary_registry_failure_does_not_stick_streaming(tk_root) -> None:
    class BadRegistry(StubRegistry):
        def get(self, name: str) -> StubClient:
            raise RuntimeError("模型不可用")

    service = GameService(user_color=1)
    service.config.model_name = "stub"
    mw = MainWindow(tk_root, service, CommentaryService(), BadRegistry())

    mw._user_result = TurnResult(move=Move(7, 7), color=1, game_over=False)
    mw._start_commentary(TurnResult(move=Move(7, 8), color=-1, game_over=False))

    assert _pump_until(tk_root, lambda: "解说不可用" in mw.panel.text.get("1.0", "end"))
    assert mw.panel.streaming is False
