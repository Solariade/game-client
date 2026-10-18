"""评估函数单测：棋型识别与评分单调性。"""

from __future__ import annotations

from app.ai.gomoku.evaluator import (
    FIVE,
    LIVE_FOUR,
    LIVE_THREE,
    RUSH_FOUR,
    evaluate,
    score_grid_for_color,
)
from app.core.base_game import Move
from app.core.gomoku.board import GomokuBoard


def score_row(cells: list[int], color: int = 1) -> int:
    """构造一行局面（居中摆放，避开棋盘边缘）并整盘评分。"""
    board = GomokuBoard()
    offset = 5
    for c, cell in enumerate(cells):
        if cell != 0:
            board.place(Move(7, offset + c), cell)
    return score_grid_for_color(board.grid, color)


class TestPatterns:
    def test_five_is_highest(self) -> None:
        assert score_row([1, 1, 1, 1, 1]) >= FIVE

    def test_live_four_beats_rush_four(self) -> None:
        board = GomokuBoard()
        for c in (4, 5, 6, 7):
            board.place(Move(7, c), 1)
        live = score_grid_for_color(board.grid, 1)
        board.place(Move(7, 8), -1)  # 一端被挡 → 冲四
        rush = score_grid_for_color(board.grid, 1)
        assert live >= LIVE_FOUR
        assert live > rush
        assert rush >= RUSH_FOUR

    def test_live_three_beats_sleep_three(self) -> None:
        board = GomokuBoard()
        for c in (5, 6, 7):
            board.place(Move(7, c), 1)
        live = score_grid_for_color(board.grid, 1)
        board.place(Move(7, 4), -1)  # 左端挡 → 眠三
        sleep = score_grid_for_color(board.grid, 1)
        assert live >= LIVE_THREE
        assert live > sleep

    def test_more_stones_score_higher(self) -> None:
        two = score_row([0, 1, 1, 0])
        three = score_row([0, 1, 1, 1, 0])
        assert three > two > 0

    def test_empty_board_scores_zero(self) -> None:
        board = GomokuBoard()
        assert score_grid_for_color(board.grid, 1) == 0
        assert score_grid_for_color(board.grid, -1) == 0


class TestEvaluate:
    def test_evaluate_prefers_own_advantage(self) -> None:
        board = GomokuBoard()
        for c in (3, 4, 5):
            board.place(Move(7, c), 1)
        for r, c in ((8, 3), (8, 4)):
            board.place(Move(r, c), -1)
        # 黑（1）活三 vs 白（-1）二连 → 从黑视角为正
        assert evaluate(board.grid, 1) > 0
        # 从白视角为负
        assert evaluate(board.grid, -1) < 0

    def test_five_wins_evaluation(self) -> None:
        board = GomokuBoard()
        for c in range(5):
            board.place(Move(7, c), 1)
        assert evaluate(board.grid, 1) >= FIVE
        assert evaluate(board.grid, -1) < 0
