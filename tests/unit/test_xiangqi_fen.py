"""象棋 FEN/ICCS 单测：解析、生成、往返、坐标互转。"""

from __future__ import annotations

import pytest

from app.core.base_game import Move
from app.core.xiangqi.fen import START_FEN, iccs_of, move_from_iccs, parse_fen, to_fen


class TestParseFen:
    def test_start_position(self) -> None:
        grid, side = parse_fen(START_FEN)
        assert grid[0] == ["r", "n", "b", "a", "k", "a", "b", "n", "r"]
        assert grid[2] == ["", "c", "", "", "", "", "", "c", ""]
        assert grid[3][0] == "p"
        assert grid[6][8] == "P"
        assert grid[7] == ["", "C", "", "", "", "", "", "C", ""]
        assert grid[9][4] == "K"
        assert side == 1

    def test_black_to_move(self) -> None:
        _grid, side = parse_fen(START_FEN.replace(" w ", " b "))
        assert side == -1

    def test_roundtrip_start(self) -> None:
        grid, side = parse_fen(START_FEN)
        assert to_fen(grid, side) == START_FEN

    def test_roundtrip_sparse(self) -> None:
        fen = "3k5/2P1R4/9/9/9/9/9/9/9/4K4 w - - 0 1"
        grid, side = parse_fen(fen)
        assert to_fen(grid, side) == fen

    @pytest.mark.parametrize(
        "bad",
        [
            # 只有 9 行
            "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9 w - - 0 1",
            # 非法字符
            "xnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1",
            # 某行展开 10 列
            "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABN9 w - - 0 1",
            # 行内出现 0
            "04k4/9/9/9/9/9/9/9/9/4K4 w - - 0 1",
            # 行棋方非法
            "4k4/9/9/9/9/9/9/9/9/4K4 z - - 0 1",
            # 缺行棋方
            "4k4/9/9/9/9/9/9/9/9/4K4",
        ],
    )
    def test_invalid_fen(self, bad: str) -> None:
        with pytest.raises(ValueError, match="FEN"):
            parse_fen(bad)


class TestIccs:
    def test_to_iccs(self) -> None:
        assert iccs_of(Move(7, 7, 7, 4)) == "h2e2"  # 炮二平五
        assert iccs_of(Move(9, 0, 8, 0)) == "a0a1"  # 红方左车前进一步
        assert iccs_of(Move(0, 7, 2, 6)) == "h9g7"  # 黑方 马8进7

    def test_from_iccs(self) -> None:
        assert move_from_iccs("h2e2") == Move(7, 7, 7, 4)
        assert move_from_iccs("a0a1") == Move(9, 0, 8, 0)
        assert move_from_iccs("b0c2") == Move(9, 1, 7, 2)  # 马八进七

    def test_roundtrip(self) -> None:
        for text in ("h2e2", "a0a1", "b0c2", "e9e8", "i0i9"):
            assert iccs_of(move_from_iccs(text)) == text

    def test_missing_destination(self) -> None:
        with pytest.raises(ValueError, match="终点"):
            iccs_of(Move(7, 7))

    def test_out_of_bounds(self) -> None:
        with pytest.raises(ValueError, match="越界"):
            iccs_of(Move(7, 7, 7, 9))

    @pytest.mark.parametrize("bad", ["h2e", "z9z9", "h2e20", ""])
    def test_invalid_iccs(self, bad: str) -> None:
        with pytest.raises(ValueError):
            move_from_iccs(bad)
