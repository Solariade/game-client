"""五子棋领域层单测：落子、胜负、撤销、克隆、to_text。"""

from __future__ import annotations

import pytest

from app.core.base_game import Move
from app.core.constants import EMPTY
from app.core.exceptions import GameOverError, IllegalMoveError
from app.core.gomoku.board import GomokuBoard


class TestPlace:
    def test_place_black_and_white(self, board: GomokuBoard) -> None:
        board.place(Move(7, 7), 1)
        board.place(Move(8, 8), -1)
        assert board.grid[7][7] == 1
        assert board.grid[8][8] == -1
        assert board.moves_count == 2

    def test_place_out_of_bounds(self, board: GomokuBoard) -> None:
        with pytest.raises(IllegalMoveError):
            board.place(Move(15, 0), 1)
        with pytest.raises(IllegalMoveError):
            board.place(Move(-1, 3), 1)

    def test_place_on_occupied(self, board: GomokuBoard) -> None:
        board.place(Move(0, 0), 1)
        with pytest.raises(IllegalMoveError):
            board.place(Move(0, 0), -1)

    def test_place_invalid_color(self, board: GomokuBoard) -> None:
        with pytest.raises(IllegalMoveError):
            board.place(Move(0, 0), 2)

    def test_place_after_game_over(self, board: GomokuBoard) -> None:
        for i in range(5):
            board.place(Move(7, i), 1)
            if i < 4:
                board.place(Move(8, i), -1)
        assert board.winner == 1
        with pytest.raises(GameOverError):
            board.place(Move(0, 0), -1)


class TestWin:
    @pytest.mark.parametrize(
        ("moves", "color", "win"),
        [
            # 横五连
            ([(7, 3), (7, 4), (7, 5), (7, 6), (7, 7)], 1, True),
            # 竖四连不成五
            ([(5, 5), (6, 5), (7, 5), (8, 5)], 1, False),
            # 斜五连（右下）
            ([(0, 0), (1, 1), (2, 2), (3, 3), (4, 4)], -1, True),
            # 斜五连（左下）
            ([(4, 10), (5, 9), (6, 8), (7, 7), (8, 6)], 1, True),
            # 断开的横排不成五
            ([(7, 3), (7, 4), (7, 6), (7, 7), (7, 8)], 1, False),
        ],
    )
    def test_win_detection(self, board: GomokuBoard, moves, color: int, win: bool) -> None:
        for r, c in moves:
            board.place(Move(r, c), color)
        assert (board.winner == color) is win
        assert board.check_win(Move(*moves[-1])) is win

    def test_win_line_coords(self, board: GomokuBoard) -> None:
        for c in range(5):
            board.place(Move(7, c), 1)
        line = board.win_line()
        assert line is not None
        assert {m.row for m in line} == {7}
        assert sorted(m.col for m in line) == [0, 1, 2, 3, 4]

    def test_win_line_none_when_no_win(self, board: GomokuBoard) -> None:
        board.place(Move(7, 7), 1)
        assert board.win_line() is None


class TestUndo:
    def test_undo_restores_cell(self, board: GomokuBoard) -> None:
        board.place(Move(3, 3), 1)
        move = board.undo()
        assert (move.row, move.col) == (3, 3)
        assert board.grid[3][3] == EMPTY
        assert board.moves_count == 0

    def test_undo_empty_board_raises(self, board: GomokuBoard) -> None:
        with pytest.raises(IllegalMoveError):
            board.undo()

    def test_undo_clears_winner(self, board: GomokuBoard) -> None:
        for c in range(5):
            board.place(Move(7, c), 1)
        assert board.winner == 1
        board.undo()
        assert board.winner is None


class TestClone:
    def test_clone_is_independent(self, board: GomokuBoard) -> None:
        board.place(Move(5, 5), 1)
        copy = board.clone()
        copy.place(Move(0, 0), -1)
        assert board.grid[0][0] == EMPTY
        assert copy.grid[5][5] == 1
        assert board.moves_count == 1
        assert copy.moves_count == 2


class TestTextAndMoves:
    def test_to_text_format(self, board: GomokuBoard) -> None:
        board.place(Move(0, 0), 1)
        board.place(Move(14, 14), -1)
        text = board.to_text()
        assert "A B C D E F G H I J K L M N O" in text
        assert " 1  1 0 0 0" in text
        assert "15  0 0 0 0 0 0 0 0 0 0 0 0 0 0 2" in text
        assert "00行" not in text  # 行号从 1 开始，与建议落子格式一致

    def test_to_text_columns_align_with_header(self, board: GomokuBoard) -> None:
        """空格分隔后，每列的 0/1/2 应与表头字母严格对齐（H8 → 第 8 列）。"""
        board.place(Move(7, 7), 1)
        lines = board.to_text().splitlines()
        header_cols = lines[0].split()
        row8_cells = lines[8].split()[1:]  # 跳过行号 "8"
        assert header_cols == list("ABCDEFGHIJKLMNO")
        assert len(row8_cells) == 15
        assert row8_cells[header_cols.index("H")] == "1"
        assert row8_cells.count("1") == 1

    def test_candidate_moves_empty_board_is_center(self, board: GomokuBoard) -> None:
        assert board.candidate_moves() == [Move(7, 7)]

    def test_candidate_moves_near_stones(self, board: GomokuBoard) -> None:
        board.place(Move(7, 7), 1)
        moves = board.candidate_moves(distance=1)
        assert Move(7, 8) in moves
        assert Move(0, 0) not in moves

    def test_is_full(self) -> None:
        small = GomokuBoard(size=3)
        for r in range(3):
            for c in range(3):
                small.place(Move(r, c), 1 if (r + c) % 2 == 0 else -1)
        assert small.is_full()
