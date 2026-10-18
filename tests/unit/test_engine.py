"""本地引擎单测：必胜/必挡/开局行为。"""

from __future__ import annotations

import pytest

from app.ai.difficulty import DIFFICULTY_DEPTH, Difficulty, depth_of
from app.ai.gomoku.engine import GomokuEngine
from app.core.base_game import Move
from app.core.gomoku.board import GomokuBoard


class TestDifficulty:
    def test_depth_mapping(self) -> None:
        assert depth_of(Difficulty.EASY) == 2
        assert depth_of(Difficulty.MEDIUM) == 3
        assert depth_of(Difficulty.HARD) == 4
        assert depth_of(Difficulty.EXPERT) == 5
        assert len(DIFFICULTY_DEPTH) == 4


class TestEngineBehavior:
    def test_empty_board_plays_center(self) -> None:
        engine = GomokuEngine()
        move = engine.search(GomokuBoard(), depth=1)
        assert (move.row, move.col) == (7, 7)

    def test_takes_immediate_win(self) -> None:
        """AI 黑已有横四（两端开放位在两侧），应直接补五。"""
        board = GomokuBoard()
        for c in (4, 5, 6, 7):
            board.place(Move(7, c), 1)
        # 白两子无关紧要处
        board.place(Move(0, 0), -1)
        board.place(Move(1, 0), -1)
        engine = GomokuEngine()
        move = engine.search(board, depth=2, ai_color=1)
        assert (move.row, move.col) in {(7, 3), (7, 8)}

    def test_blocks_opponent_four(self) -> None:
        """白（用户）已有活四，AI 必须堵（无论堵哪端都不成五，但必须挡）。"""
        board = GomokuBoard()
        for c in (5, 6, 7, 8):
            board.place(Move(7, c), -1)
        board.place(Move(8, 8), 1)
        board.place(Move(9, 9), 1)
        engine = GomokuEngine()
        move = engine.search(board, depth=2, ai_color=1)
        assert (move.row, move.col) in {(7, 4), (7, 9)}

    def test_blocks_opponent_open_three(self) -> None:
        """用户黑活三（.BBB.），AI 深度 3 应落在两端或中隔之一堵截。"""
        board = GomokuBoard()
        board.place(Move(7, 6), 1)
        board.place(Move(7, 7), 1)
        board.place(Move(7, 8), 1)
        # AI（白）此前两手无关紧要
        board.place(Move(0, 0), -1)
        board.place(Move(1, 1), -1)
        engine = GomokuEngine()
        move = engine.search(board, depth=3, ai_color=-1)
        blocking = {(7, 5), (7, 9), (6, 6), (6, 8), (8, 6), (8, 8), (7, 7)}
        assert (move.row, move.col) in blocking, f"未堵活三: {move}"

    def test_blocks_open_three_instead_of_racing(self) -> None:
        """黑活三、白也有做活三的机会：白必须堵，不能各做各的四。

        回归用例：旧评估在叶子节点只看静态棋型，双方都有四时会把
        “轮到自己走” 的必胜方算成均势，导致 AI 走出自己冲四、
        却被对手先成五的漏着。
        """
        board = GomokuBoard()
        board.place(Move(7, 7), 1)  # 黑 H8
        board.place(Move(6, 6), -1)  # 白 G7
        board.place(Move(5, 7), 1)  # 黑 H6
        board.place(Move(7, 6), -1)  # 白 G8
        board.place(Move(6, 7), 1)  # 黑 H7 → 活三
        engine = GomokuEngine()
        move = engine.search(board, depth=3, ai_color=-1)
        assert (move.row, move.col) in {(4, 7), (8, 7)}, f"未堵活三: {move}"

    def test_invalid_depth_raises(self) -> None:
        with pytest.raises(ValueError):
            GomokuEngine().search(GomokuBoard(), depth=0)

    def test_wrong_board_type_raises(self) -> None:
        class FakeGame:
            pass

        with pytest.raises(TypeError):
            GomokuEngine().search(FakeGame(), depth=2)  # type: ignore[arg-type]

    def test_search_does_not_mutate_board(self) -> None:
        board = GomokuBoard()
        board.place(Move(7, 7), 1)
        board.place(Move(8, 8), -1)
        before = [row[:] for row in board.grid]
        GomokuEngine().search(board, depth=2, ai_color=1)
        assert board.grid == before
        assert board.moves_count == 2
