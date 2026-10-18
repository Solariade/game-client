"""从解说全文中解析建议落子（「建议落子：XN」→ Move）。"""

from __future__ import annotations

import re

from app.core.base_game import Move

# 列 A~O + 行 1~15；允许全角冒号与大小写字母，取最后一次出现。
# 行号后用 (?![0-9]) 而非 \b，避免数字后紧跟中文字符时误判边界。
_SUGGESTION_RE = re.compile(r"建议落子[：:]\s*([A-Oa-o])\s*([1-9]|1[0-5])(?![0-9])")


def format_coord(move: Move) -> str:
    """Move → A1 风格坐标：列 A~O + 行 1~15。"""
    return f"{chr(ord('A') + move.col)}{move.row + 1}"


def parse_suggested_move(text: str, board_size: int = 15) -> Move | None:
    """解析文本中最后一个「建议落子：XN」；无匹配或越界返回 None。"""
    matches = _SUGGESTION_RE.findall(text)
    if not matches:
        return None
    letter, num = matches[-1]
    col = ord(letter.upper()) - ord("A")
    row = int(num) - 1
    if not (0 <= row < board_size and 0 <= col < board_size):
        return None
    return Move(row, col)
