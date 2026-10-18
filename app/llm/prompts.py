"""提示词模板：按棋种分模板（未来象棋新增 XIANGQI_PROMPT 即可）。"""

from __future__ import annotations

from app.core.base_game import Move
from app.core.gomoku.board import GomokuBoard
from app.llm.suggestion import format_coord

GOMOKU_PROMPT = """你正在解说一局五子棋（15×15，黑先，无禁手）。

坐标约定：列从左到右为字母 A~O，行从上到下为数字 1~15。
下面棋盘的顶部标有列字母、左侧标有行号，坐标与程序给出的建议格式一致。

当前局面（0=空位，1=黑子，2=白子）：
{board_text}

刚才用户（{user_color_name}）落子在 {user_move}，
我方 AI（{ai_color_name}）落子在 {ai_move}，现在轮到用户（{user_color_name}）走棋。

对局记录（按落子顺序，最后一条是刚才 AI 的落子）：
{move_history}

请按以下三点解说：
1. 拆解用户这一步的意图（进攻/防守/布局，连成了什么棋型）；
2. 解释 AI 走在 {ai_move} 的理由（堵截、做棋型或争先手）；
3. 预判接下来 2~3 步双方最可能的走法与争夺焦点。

要求：分三段，每段一两句话，总长不超过 150 字；
不要输出棋盘图、Markdown，也不要输出落子建议（建议由程序单独给出）。"""


def _history_text(board: GomokuBoard, user_color: int) -> str:
    """按落子顺序列出全部着法，方便模型核对哪些坐标已被占用。"""
    lines = []
    for i, (move, color) in enumerate(board.history(), 1):
        side = "黑" if color == 1 else "白"
        who = "用户" if color == user_color else "AI"
        lines.append(f"{i}. {side}（{who}）{format_coord(move)}")
    return "\n".join(lines)


def build_gomoku_prompt(
    board: GomokuBoard,
    user_move: Move,
    ai_move: Move,
    user_color: int,
) -> str:
    """组装五子棋解说提示词（只解说局面，不负责建议落子）。"""
    ai_color = -user_color
    user_color_name = "黑棋" if user_color == 1 else "白棋"
    ai_color_name = "黑棋" if ai_color == 1 else "白棋"
    return GOMOKU_PROMPT.format(
        board_text=board.to_text(),
        move_history=_history_text(board, user_color),
        user_color_name=user_color_name,
        ai_color_name=ai_color_name,
        user_move=format_coord(user_move),
        ai_move=format_coord(ai_move),
    )
