"""GameService 编排逻辑单测（无 DB / 注入桩引擎）。"""

from __future__ import annotations

import pytest

from app.ai.base_engine import BaseEngine
from app.core.base_game import Move
from app.core.gomoku.board import GomokuBoard
from app.services.game_service import GameService


class ScriptedEngine(BaseEngine):
    """按脚本依次落子的桩引擎。"""

    def __init__(self, moves: list[tuple[int, int]]) -> None:
        self.moves = moves
        self.i = 0
        self.last_color: int | None = None
        self.last_depth: int | None = None

    def search(self, game, depth: int, ai_color: int | None = None) -> Move:  # type: ignore[override]
        self.last_color = ai_color
        self.last_depth = depth
        move = Move(*self.moves[self.i])
        self.i += 1
        return move


class TestTurnFlow:
    def test_user_goes_first(self) -> None:
        service = GameService(board=GomokuBoard(), user_color=1)
        assert service.user_turn is True
        result = service.user_move(7, 7)
        assert (result.move.row, result.move.col) == (7, 7)
        assert result.color == 1
        assert result.game_over is False
        assert service.user_turn is False  # 轮到 AI

    def test_ai_turn_returns_result(self) -> None:
        service = GameService(board=GomokuBoard(), engine=ScriptedEngine([(7, 8)]), user_color=1)
        service.user_move(7, 7)
        result = service.take_ai_turn()
        assert (result.move.row, result.move.col) == (7, 8)
        assert result.color == -1
        assert service.user_turn is True
        # 引擎必须显式收到 AI 棋色，而不是靠“上一手对手”推断
        assert service.engine.last_color == -1  # type: ignore[attr-defined]

    def test_suggest_for_user_uses_engine_and_user_color(self) -> None:
        """本地建议不依赖 LLM：AI 落子后由引擎以用户棋色、建议深度搜索。"""
        service = GameService(
            board=GomokuBoard(), engine=ScriptedEngine([(7, 8), (6, 6)]), user_color=1
        )
        service.user_move(7, 7)
        service.take_ai_turn()
        assert service.user_turn is True
        suggestion = service.suggest_for_user()
        assert suggestion == Move(6, 6)
        assert service.engine.last_color == 1  # type: ignore[attr-defined]
        # 默认中等（AI 深度 3）→ 建议深度 4：高一层才真正提高胜率
        assert service.engine.last_depth == 4  # type: ignore[attr-defined]

    def test_suggestion_depth_is_one_above_difficulty(self) -> None:
        service = GameService(board=GomokuBoard(), engine=ScriptedEngine([(6, 6)]), user_color=1)
        service.config.difficulty_depth = 2
        assert service.suggestion_depth == 3
        assert service.suggest_for_user() == Move(6, 6)
        assert service.engine.last_depth == 3  # type: ignore[attr-defined]

    def test_suggest_for_user_hard_is_one_level_above_ai(self) -> None:
        """困难 AI 为 4 层，建议用 5 层。"""
        service = GameService(board=GomokuBoard(), engine=ScriptedEngine([(6, 6)]), user_color=1)
        service.config.difficulty_depth = 4
        assert service.suggestion_depth == 5
        assert service.suggest_for_user() == Move(6, 6)
        assert service.engine.last_depth == 5  # type: ignore[attr-defined]

    def test_suggest_for_user_expert_caps_at_five(self) -> None:
        """专家 AI 已是 5 层，建议保持 5 层（不再加一）。"""
        service = GameService(board=GomokuBoard(), engine=ScriptedEngine([(6, 6)]), user_color=1)
        service.config.difficulty_depth = 5
        assert service.suggestion_depth == 5
        assert service.suggest_for_user() == Move(6, 6)
        assert service.engine.last_depth == 5  # type: ignore[attr-defined]

    def test_suggest_for_user_returns_none_when_not_user_turn(self) -> None:
        # 用户执白且空盘 → 轮到 AI 先行，不给用户建议
        service = GameService(board=GomokuBoard(), engine=ScriptedEngine([(7, 8)]), user_color=-1)
        assert service.suggest_for_user() is None

    def test_suggest_for_user_returns_none_after_game_over(self) -> None:
        service = GameService(board=GomokuBoard(), engine=ScriptedEngine([]), user_color=1)
        for c in range(5):
            service.user_move(7, c)
        assert service.game_over is True
        assert service.suggest_for_user() is None

    def test_ai_turn_requires_engine(self) -> None:
        service = GameService(board=GomokuBoard(), user_color=1)
        service.user_move(7, 7)
        try:
            service.take_ai_turn()
            raise AssertionError("应当抛 RuntimeError")
        except RuntimeError as exc:
            assert "引擎" in str(exc)

    def test_set_user_color(self) -> None:
        service = GameService(board=GomokuBoard(), user_color=1)
        assert service.user_turn is True  # 空盘黑先，用户执黑
        service.set_user_color(-1)
        assert service.user_color == -1
        assert service.ai_color == 1
        assert service.user_turn is False  # 空盘时 AI（黑）先行

    def test_set_user_color_rejects_invalid(self) -> None:
        service = GameService(board=GomokuBoard(), user_color=1)
        with pytest.raises(ValueError):
            service.set_user_color(2)

    def test_user_wins_sets_game_over(self) -> None:
        service = GameService(board=GomokuBoard(), user_color=1)
        # 用户连续五子（user_move 不校验轮次，直接绕过 AI 回合）
        for c in range(4):
            service.user_move(7, c)
        result = service.user_move(7, 4)
        assert result.game_over is True
        assert result.winner == 1
        assert service.game_over is True
        assert service.user_turn is False
        assert result.win_line is not None

    def test_full_board_draw(self) -> None:
        small = GomokuBoard(size=3)
        service = GameService(
            board=small,
            engine=ScriptedEngine([(0, 1), (1, 0), (1, 2), (2, 1)]),
            user_color=1,
        )
        # 交替填满 3×3（3×3 盘无法成五，必平局）
        result = None
        for r in range(3):
            for c in range(3):
                if service.user_turn:
                    result = service.user_move(r, c)
                else:
                    result = service.take_ai_turn()
        assert result is not None
        assert result.game_over is True
        assert result.winner is None
