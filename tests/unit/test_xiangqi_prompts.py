"""象棋解说提示词单测：记法重演、评分文案、PV 转换。"""

from __future__ import annotations

from app.ai.xiangqi.engine import EngineEval
from app.core.base_game import Move
from app.core.xiangqi.board import XiangqiBoard
from app.llm.prompts import build_xiangqi_prompt, score_display

# 炮二平五（红）/ 马8进7（黑）
H2E2 = Move(7, 7, 7, 4)
H9G7 = Move(0, 7, 2, 6)


def played_board() -> XiangqiBoard:
    board = XiangqiBoard()
    board.place(H2E2, 1)
    board.place(H9G7, -1)
    return board


class TestHistoryNotations:
    def test_standard_opening(self) -> None:
        assert played_board().history_notations() == ["炮二平五", "马8进7"]

    def test_empty_history(self) -> None:
        assert XiangqiBoard().history_notations() == []


class TestScoreDisplay:
    def test_none(self) -> None:
        assert "暂无" in score_display(None)

    def test_centipawn(self) -> None:
        assert "+35" in score_display(EngineEval(bestmove="h2e2", score_cp=35))
        assert "-120" in score_display(EngineEval(bestmove="h2e2", score_cp=-120))

    def test_mate_signs(self) -> None:
        assert score_display(EngineEval(bestmove="h2e2", mate_in=3)) == "红方 3 步内可将死"
        assert score_display(EngineEval(bestmove="h2e2", mate_in=-2)) == "黑方 2 步内可将死"


class TestBuildXiangqiPrompt:
    def test_contains_fen_notations_and_eval(self) -> None:
        board = played_board()
        prompt = build_xiangqi_prompt(
            board, H2E2, H9G7, user_color=1, engine_eval=EngineEval(bestmove="h0g2", score_cp=35)
        )
        assert board.to_fen() in prompt
        assert "炮二平五" in prompt
        assert "马8进7" in prompt
        assert "红方视角 +35" in prompt
        assert "用户（红方）" in prompt
        assert "AI（黑方）" in prompt
        assert "1. 红（用户）炮二平五" in prompt
        assert "2. 黑（AI）马8进7" in prompt

    def test_pv_translated_to_notation(self) -> None:
        # 炮二平五 马8进7 之后：马二进三（h0g2）、车9平8（i9h9）
        prompt = build_xiangqi_prompt(
            played_board(),
            H2E2,
            H9G7,
            user_color=1,
            engine_eval=EngineEval(bestmove="h0g2", score_cp=0, pv=["h0g2", "i9h9"]),
        )
        assert "马二进三、车9平8" in prompt

    def test_pv_truncated_on_illegal_tail(self) -> None:
        prompt = build_xiangqi_prompt(
            played_board(),
            H2E2,
            H9G7,
            user_color=1,
            engine_eval=EngineEval(bestmove="h0g2", score_cp=0, pv=["h0g2", "zzzz", "h0g2"]),
        )
        assert "马二进三" in prompt
        assert "马二进三、马二进三" not in prompt  # 非法尾部被截断，不重演

    def test_pv_from_empty_square_stops(self) -> None:
        # b6 是空位（黑卒都在 1/3/5/7/9 列），从空位起手的变例着法直接截断
        prompt = build_xiangqi_prompt(
            played_board(),
            H2E2,
            H9G7,
            user_color=1,
            engine_eval=EngineEval(bestmove="h0g2", score_cp=0, pv=["b6b5", "h0g2"]),
        )
        assert "暂无" in prompt

    def test_no_eval_and_no_pv(self) -> None:
        prompt = build_xiangqi_prompt(played_board(), H2E2, H9G7, user_color=1)
        assert "暂无（引擎未给出评估）" in prompt

    def test_user_black_wording(self) -> None:
        board = XiangqiBoard()
        # 红先马二进三（h0g2）、黑应炮8平5（h7e7），用户执黑
        red = Move(9, 7, 7, 6)
        black = Move(2, 7, 2, 4)
        board.place(red, 1)
        board.place(black, -1)
        prompt = build_xiangqi_prompt(board, red, black, user_color=-1)
        assert "用户（黑方）" in prompt
        assert "AI（红方）" in prompt
        assert "马二进三" in prompt
        assert "炮8平5" in prompt
