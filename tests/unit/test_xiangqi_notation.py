"""中文着法记法单测：纵线、进退平、步数、前中后消歧。"""

from __future__ import annotations

from app.core.base_game import Move
from app.core.xiangqi.fen import START_FEN, parse_fen
from app.core.xiangqi.notation import move_text


def grid_of(fen: str) -> list[list[str]]:
    return parse_fen(fen)[0]


class TestNotation:
    def test_red_classics(self) -> None:
        grid = grid_of(START_FEN)
        assert move_text(grid, Move(7, 7, 7, 4)) == "炮二平五"
        assert move_text(grid, Move(7, 1, 7, 4)) == "炮八平五"
        assert move_text(grid, Move(9, 7, 7, 6)) == "马二进三"
        assert move_text(grid, Move(9, 1, 7, 2)) == "马八进七"

    def test_black_classics(self) -> None:
        grid = grid_of(START_FEN)
        assert move_text(grid, Move(0, 7, 2, 6)) == "马8进7"
        assert move_text(grid, Move(0, 1, 2, 2)) == "马2进3"

    def test_rook_flat_and_advance(self) -> None:
        grid = grid_of("r3k4/9/9/9/9/9/9/9/9/R3K4 w - - 0 1")
        assert move_text(grid, Move(0, 0, 1, 0)) == "车1进1"
        assert move_text(grid, Move(9, 0, 8, 0)) == "车九进一"

    def test_pawn_steps(self) -> None:
        red = grid_of("3k5/9/9/9/9/9/4P4/9/9/4K4 w - - 0 1")
        assert move_text(red, Move(6, 4, 5, 4)) == "兵五进一"
        black = grid_of("3k5/9/9/2p6/9/9/9/9/9/4K4 w - - 0 1")
        assert move_text(black, Move(3, 2, 4, 2)) == "卒3进1"

    def test_knight_retreat(self) -> None:
        grid = grid_of("3k5/9/9/9/9/9/9/6N2/9/3K5 w - - 0 1")
        assert move_text(grid, Move(7, 6, 9, 7)) == "马三退二"

    def test_front_back_disambiguation(self) -> None:
        grid = grid_of("3k5/9/9/9/9/7C1/9/7C1/9/4K4 w - - 0 1")
        assert move_text(grid, Move(5, 7, 5, 4)) == "前炮平五"  # 靠近黑方者为前
        assert move_text(grid, Move(7, 7, 7, 4)) == "后炮平五"

    def test_three_pawns_front_middle_back(self) -> None:
        grid = grid_of("3k5/9/9/2p6/9/2p6/9/2p6/9/4K4 w - - 0 1")
        assert move_text(grid, Move(7, 2, 8, 2)) == "前卒进1"  # 黑方靠近红方者为前
        assert move_text(grid, Move(5, 2, 6, 2)) == "中卒进1"
        assert move_text(grid, Move(3, 2, 4, 2)) == "后卒进1"
