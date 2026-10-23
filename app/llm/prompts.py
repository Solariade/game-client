"""提示词模板：按棋种分模板（五子棋 / 象棋）。"""

from __future__ import annotations

from app.ai.xiangqi.engine import EngineEval
from app.core.base_game import Move
from app.core.gomoku.board import GomokuBoard
from app.core.xiangqi import rules
from app.core.xiangqi.board import XiangqiBoard
from app.core.xiangqi.fen import move_from_iccs
from app.core.xiangqi.notation import move_text
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


XIANGQI_PROMPT = """你正在解说一局中国象棋（红先）。

当前局面 FEN：{fen}
（FEN 大写为红、小写为黑；行从黑方底线到红方底线，列 a~i 从红方左侧数）

棋盘示意（左侧数字为 ICCS 行号 9→0，红方在最下方；对照：K帅 A仕 B相 N马 R车 C炮 P兵，小写为黑方将士象马车炮卒）：
{board_text}

着法记录（中文记法，按行棋顺序）：
{move_history}

刚才用户（{user_color_name}）走 {user_move}，AI（{ai_color_name}）走 {ai_move}，现在轮到用户（{user_color_name}）行棋。

引擎评估（AI 选择上一着时的判断）：{score_text}；主要变例：{pv_text}

请按以下三点解说：
1. 拆解用户这一着的意图（进攻/防守/兑子/运子）；
2. 解释 AI 走 {ai_move} 的理由（应将、抢攻或布局）；
3. 预判接下来 2~3 步双方最可能的着法与争夺焦点。

要求：分三段，每段一两句话，总长不超过 150 字；
不要输出棋盘图、Markdown，也不要输出走子建议（建议由程序单独给出）。"""


def _xiangqi_history_text(board: XiangqiBoard, user_color: int) -> str:
    """着法记录：序号 + 红黑 + 谁 + 中文记法。"""
    lines = []
    notations = board.history_notations()
    for i, ((_move, color), text) in enumerate(zip(board.history(), notations, strict=True), 1):
        side = "红" if color == rules.RED else "黑"
        who = "用户" if color == user_color else "AI"
        lines.append(f"{i}. {side}（{who}）{text}")
    return "\n".join(lines) if lines else "（对局刚开始，尚无着法）"


def score_display(eval: EngineEval | None) -> str:
    """引擎评估 → 展示文案（mate 优先，其次厘兵分；红方视角）。"""
    if eval is None:
        return "暂无（引擎未给出评估）"
    if eval.mate_in is not None:
        side = "红方" if eval.mate_in > 0 else "黑方"
        return f"{side} {abs(eval.mate_in)} 步内可将死"
    return f"红方视角 {eval.score_cp:+d} 厘兵（正数红优、负数黑优）"


def score_brief(eval: EngineEval | None) -> str:
    """面板用的短评估文案：``红方优 0.36 兵`` / ``黑方 3 步内将死``。"""
    if eval is None:
        return "暂无评估"
    if eval.mate_in is not None:
        side = "红方" if eval.mate_in > 0 else "黑方"
        return f"{side} {abs(eval.mate_in)} 步内将死"
    if eval.score_cp == 0:
        return "均势"
    side = "红方" if eval.score_cp > 0 else "黑方"
    return f"{side}优 {abs(eval.score_cp) / 100:.2f} 兵"


def _pv_text(board: XiangqiBoard, pv: list[str], limit: int = 6) -> str:
    """主要变例 ICCS → 中文记法：在当前局面上重演，遇到非法着法即截断。"""
    if not pv:
        return "暂无"
    grid = [row[:] for row in board.grid]
    texts: list[str] = []
    for iccs in pv[:limit]:
        try:
            move = move_from_iccs(iccs)
            if not grid[move.row][move.col]:
                break
            texts.append(move_text(grid, move))
            rules.apply_move(grid, move)
        except (ValueError, KeyError, IndexError):
            break
    return "、".join(texts) if texts else "暂无"


def build_xiangqi_prompt(
    board: XiangqiBoard,
    user_move: Move,
    ai_move: Move,
    user_color: int,
    engine_eval: EngineEval | None = None,
) -> str:
    """组装象棋解说提示词：FEN + 中文记法 + 引擎评估 + 主要变例。

    约定在用户与 AI 的着法都已落盘后调用（记法取历史末两条）。
    """
    ai_color = -user_color
    notations = board.history_notations()
    user_text = notations[-2] if len(notations) >= 2 else "（首着）"
    ai_text = notations[-1] if notations else "（首着）"
    return XIANGQI_PROMPT.format(
        fen=board.to_fen(),
        board_text=board.to_text(),
        move_history=_xiangqi_history_text(board, user_color),
        user_color_name="红方" if user_color == rules.RED else "黑方",
        ai_color_name="红方" if ai_color == rules.RED else "黑方",
        user_move=user_text,
        ai_move=ai_text,
        score_text=score_display(engine_eval),
        pv_text=_pv_text(board, engine_eval.pv if engine_eval else []),
    )
