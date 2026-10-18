"""建议落子解析单测：「建议落子：XN」→ Move。"""

from __future__ import annotations

from app.core.base_game import Move
from app.llm.suggestion import format_coord, parse_suggested_move


def test_format_coord_is_inverse_of_parse() -> None:
    for move in (Move(0, 0), Move(7, 7), Move(14, 14), Move(6, 8)):
        assert parse_suggested_move(f"建议落子：{format_coord(move)}") == move


def test_parse_basic() -> None:
    assert parse_suggested_move("黑落天元。建议落子：H8") == Move(7, 7)


def test_parse_fullwidth_colon_and_lowercase() -> None:
    assert parse_suggested_move("建议落子:  h9") == Move(8, 7)


def test_parse_row_15_and_1() -> None:
    assert parse_suggested_move("建议落子：A15") == Move(14, 0)
    assert parse_suggested_move("建议落子：O1") == Move(0, 14)


def test_parse_takes_last_match() -> None:
    text = "建议落子：H8 也可以考虑。最终建议落子：C3"
    assert parse_suggested_move(text) == Move(2, 2)


def test_parse_rejects_out_of_board() -> None:
    assert parse_suggested_move("建议落子：P5") is None  # 列越界
    assert parse_suggested_move("建议落子：H16") is None  # 行越界
    assert parse_suggested_move("建议落子：H0") is None


def test_parse_no_marker_returns_none() -> None:
    assert parse_suggested_move("这步棋走得稳健，防守到位。") is None
    assert parse_suggested_move("建议下在 H8") is None  # 格式不符，不误匹配
