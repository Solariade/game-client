"""象棋棋盘单测：落子/撤销/胜负/克隆/FEN/文本化/建议校验。"""

from __future__ import annotations

import pytest

from app.core.base_game import Move
from app.core.exceptions import GameOverError, IllegalMoveError
from app.core.xiangqi.board import XiangqiBoard
from app.core.xiangqi.fen import START_FEN


class TestPlace:
    def test_place_cannon(self) -> None:
        board = XiangqiBoard()
        board.place(Move(7, 7, 7, 4), 1)  # 炮二平五
        assert board.grid[7][4] == "C"
        assert board.grid[7][7] == ""
        assert board.side_to_move == -1
        assert board.moves_count == 1

    def test_not_your_turn(self) -> None:
        board = XiangqiBoard()
        board.place(Move(7, 7, 7, 4), 1)
        with pytest.raises(IllegalMoveError, match="没轮到"):
            board.place(Move(7, 1, 7, 4), 1)

    def test_invalid_color(self) -> None:
        with pytest.raises(IllegalMoveError, match="棋色"):
            XiangqiBoard().place(Move(7, 7, 7, 4), 2)

    def test_missing_destination(self) -> None:
        with pytest.raises(IllegalMoveError, match="终点"):
            XiangqiBoard().place(Move(7, 7), 1)

    def test_moving_enemy_piece(self) -> None:
        with pytest.raises(IllegalMoveError, match="本方棋子"):
            XiangqiBoard().place(Move(0, 7, 2, 6), 1)

    def test_illegal_target(self) -> None:
        with pytest.raises(IllegalMoveError, match="不合法"):
            XiangqiBoard().place(Move(7, 7, 5, 5), 1)  # 炮不走斜线

    def test_knight_leg_rejected(self) -> None:
        board = XiangqiBoard()
        with pytest.raises(IllegalMoveError):
            board.place(Move(9, 1, 8, 3), 1)  # 相 (9,2) 蹩马腿


class TestUndo:
    def test_undo_empty_board(self) -> None:
        with pytest.raises(IllegalMoveError, match="撤销"):
            XiangqiBoard().undo()

    def test_capture_and_undo_restores(self) -> None:
        board = XiangqiBoard("4k4/9/9/9/9/p8/9/9/9/R2K5 w - - 0 1")
        board.place(Move(9, 0, 5, 0), 1)  # 车吃黑卒
        assert board.grid[5][0] == "R"
        assert board.moves_count == 1
        board.undo()
        assert board.grid[5][0] == "p"
        assert board.grid[9][0] == "R"
        assert board.side_to_move == 1
        assert board.moves_count == 0

    def test_undo_after_game_over_clears_state(self) -> None:
        board = XiangqiBoard("4k4/9/2N3N2/9/4R4/9/9/9/9/3K5 w - - 0 1")
        board.place(Move(4, 4, 2, 4), 1)
        assert board.winner == 1
        board.undo()
        assert board.winner is None
        assert board.end_reason is None
        assert board.side_to_move == 1


class TestGameEnd:
    def test_checkmate(self) -> None:
        board = XiangqiBoard("4k4/9/2N3N2/9/4R4/9/9/9/9/3K5 w - - 0 1")
        result = board.place(Move(4, 4, 2, 4), 1)  # 车上至 (2,4) 双马成杀
        assert result is None
        assert board.winner == 1
        assert board.end_reason == "checkmate"
        assert board.check_win(Move(4, 4, 2, 4))
        with pytest.raises(GameOverError):
            board.place(Move(0, 4, 0, 3), -1)

    def test_stalemate(self) -> None:
        board = XiangqiBoard("3k5/2P6/9/9/4R4/9/9/9/9/4K4 w - - 0 1")
        board.place(Move(4, 4, 1, 4), 1)  # 车上提封锁，困毙黑将
        assert board.winner == 1
        assert board.end_reason == "stalemate"

    def test_is_full_always_false(self) -> None:
        assert XiangqiBoard().is_full() is False


class TestState:
    def test_start_fen_roundtrip(self) -> None:
        board = XiangqiBoard()
        assert board.to_fen() == START_FEN
        board.place(Move(7, 7, 7, 4), 1)
        fen = board.to_fen()
        assert " b " in fen
        reloaded = XiangqiBoard(fen)
        assert reloaded.to_fen() == fen

    def test_clone_is_independent(self) -> None:
        board = XiangqiBoard()
        copy = board.clone()
        copy.place(Move(7, 7, 7, 4), 1)
        assert board.moves_count == 0
        assert copy.moves_count == 1
        assert board.grid[7][4] == ""
        assert copy.grid[7][4] == "C"

    def test_history_and_move_history(self) -> None:
        board = XiangqiBoard()
        board.place(Move(7, 7, 7, 4), 1)
        board.place(Move(0, 7, 2, 6), -1)  # 黑方 马8进7
        assert board.move_history == [Move(7, 7, 7, 4), Move(0, 7, 2, 6)]
        assert board.history() == [(Move(7, 7, 7, 4), 1), (Move(0, 7, 2, 6), -1)]
        assert board.last_move() == (Move(0, 7, 2, 6), -1)

    def test_to_text(self) -> None:
        text = XiangqiBoard().to_text()
        assert "h" in text  # 列头
        assert "行棋方：红" in text
        assert text.count("r") + text.count("R") == 4  # 双方各 2 车

    def test_is_in_check_start(self) -> None:
        assert XiangqiBoard().is_in_check() is False


class TestIsPlayable:
    def test_start_position(self) -> None:
        board = XiangqiBoard()
        assert board.is_playable(Move(7, 7, 7, 4)) is True  # 炮二平五
        assert board.is_playable(Move(7, 7, 5, 5)) is False  # 炮不走斜线
        assert board.is_playable(Move(0, 7, 2, 6)) is False  # 黑棋轮不到走
        assert board.is_playable(Move(7, 7)) is False  # 缺终点
