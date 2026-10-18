"""提示词拼接单测。"""

from __future__ import annotations

from app.core.base_game import Move
from app.core.gomoku.board import GomokuBoard
from app.llm.prompts import build_gomoku_prompt


class TestBuildGomokuPrompt:
    def test_contains_board_and_moves(self) -> None:
        board = GomokuBoard()
        board.place(Move(7, 7), 1)
        board.place(Move(8, 8), -1)
        prompt = build_gomoku_prompt(board, user_move=Move(7, 7), ai_move=Move(8, 8), user_color=1)
        assert "15×15" in prompt
        assert "H8" in prompt  # 用户走 (7,7) → 列 H 行 8
        assert "I9" in prompt  # AI 走 (8,8)
        assert "黑棋" in prompt and "白棋" in prompt
        assert "预判" in prompt

    def test_color_names_when_user_white(self) -> None:
        board = GomokuBoard()
        board.place(Move(7, 7), 1)
        board.place(Move(7, 8), -1)
        prompt = build_gomoku_prompt(board, user_move=Move(7, 8), ai_move=Move(7, 7), user_color=-1)
        # 用户执白时：用户=白棋
        assert "用户（白棋）" in prompt
        assert "AI（黑棋）" in prompt

    def test_board_text_embedded(self) -> None:
        board = GomokuBoard()
        board.place(Move(0, 0), 1)
        prompt = build_gomoku_prompt(board, user_move=Move(0, 0), ai_move=Move(1, 1), user_color=1)
        assert "A B C D E F G H I J K L M N O" in prompt
        assert " 1  1 0 0 0" in prompt
        assert "00行" not in prompt

    def test_prompt_does_not_ask_llm_for_move_suggestion(self) -> None:
        """建议落子改由本地引擎生成，提示词不再要求模型输出坐标。"""
        board = GomokuBoard()
        board.place(Move(7, 7), 1)
        board.place(Move(8, 8), -1)
        prompt = build_gomoku_prompt(board, user_move=Move(8, 8), ai_move=Move(7, 7), user_color=1)
        assert "建议落子" not in prompt
        assert "建议由程序单独给出" in prompt

    def test_prompt_contains_full_move_history_in_order(self) -> None:
        """全部着法按时间顺序给出，模型可核对哪些坐标已经被占用。"""
        board = GomokuBoard()
        board.place(Move(7, 7), 1)  # H8 用户
        board.place(Move(7, 6), -1)  # G8 AI
        board.place(Move(7, 8), 1)  # I8 用户
        board.place(Move(8, 8), -1)  # I9 AI
        prompt = build_gomoku_prompt(board, user_move=Move(7, 8), ai_move=Move(8, 8), user_color=1)
        assert "1. 黑（用户）H8" in prompt
        assert "2. 白（AI）G8" in prompt
        assert "3. 黑（用户）I8" in prompt
        assert "4. 白（AI）I9" in prompt
        assert prompt.index("1. 黑（用户）H8") < prompt.index("4. 白（AI）I9")
