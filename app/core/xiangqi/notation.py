"""中文着法记法（炮二平五 / 马8进7）：由走子前的棋盘推得。

约定：红方纵线从己方右侧数一~九（汉字），黑方从己方右侧数 1~9（数字）；
红方「进」向 row 减小方向，黑方相反。直线子（车炮帅兵）进退记步数、
平移记终点纵线；斜走子（马相仕）进退记终点纵线。
同纵线有同种己方棋子时用「前/中/后」消歧（三个以上为简化处理）。
"""

from __future__ import annotations

from app.core.base_game import Move
from app.core.xiangqi import rules

_RED_NAMES = {"K": "帅", "A": "仕", "B": "相", "N": "马", "R": "车", "C": "炮", "P": "兵"}
_BLACK_NAMES = {"K": "将", "A": "士", "B": "象", "N": "马", "R": "车", "C": "炮", "P": "卒"}
_CN_NUMERALS = "一二三四五六七八九"

# 斜走子：进/退后接「终点纵线」而非步数
_DIAGONAL_KINDS = frozenset("NBA")


def _file_text(side: int, col: int) -> str:
    """col → 该方纵线号（红汉字、黑数字）。"""
    return _CN_NUMERALS[8 - col] if side == rules.RED else str(col + 1)


def _num_text(side: int, n: int) -> str:
    """步数 → 该方数字风格（红汉字、黑阿拉伯数字）。"""
    return _CN_NUMERALS[n - 1] if side == rules.RED else str(n)


def _prefix(grid: list[list[str]], fr: int, fc: int) -> str:
    """同纵线上同种棋子的前/中/后消歧前缀（无重名者为空）。"""
    piece = grid[fr][fc]
    rows = sorted(
        (r for r in range(rules.ROWS) if grid[r][fc] == piece),
        reverse=rules.side_of(piece) == rules.BLACK,  # 「前」在列表首位
    )
    if len(rows) < 2:
        return ""
    idx = rows.index(fr)
    if len(rows) == 2:
        labels: tuple[str, ...] = ("前", "后")
    elif len(rows) == 3:
        labels = ("前", "中", "后")
    else:  # 4+ 个同线同名（多条兵线并列，罕见）：按序号简化处理
        return "" if idx >= 9 else _num_text(rules.side_of(piece), idx + 1)
    return labels[idx] if idx < len(labels) else ""


def move_text(grid: list[list[str]], move: Move) -> str:
    """走子前棋盘 grid + 着法 → 中文记法（如 ``炮二平五``）。"""
    piece = grid[move.row][move.col]
    side = rules.side_of(piece)
    kind = piece.upper()
    names = _RED_NAMES if side == rules.RED else _BLACK_NAMES
    prefix = _prefix(grid, move.row, move.col)
    head = f"{prefix}{names[kind]}" if prefix else f"{names[kind]}{_file_text(side, move.col)}"

    tr = move.to_row
    assert tr is not None and move.to_col is not None  # 调用方给的是合法着法
    dr = tr - move.row
    if dr == 0:
        return head + f"平{_file_text(side, move.to_col)}"
    word = "进" if (dr < 0) == (side == rules.RED) else "退"
    if kind in _DIAGONAL_KINDS:
        return head + f"{word}{_file_text(side, move.to_col)}"
    return head + f"{word}{_num_text(side, abs(dr))}"
