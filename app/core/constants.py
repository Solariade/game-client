"""通用常量：棋色、方向向量、坐标。"""

from __future__ import annotations

from enum import IntEnum

EMPTY = 0


class Color(IntEnum):
    """棋色：黑=1，白=-1（五子棋数组用 0 空 / 1 黑 / -1 白）。"""

    BLACK = 1
    WHITE = -1

    @property
    def opponent(self) -> Color:
        return Color.BLACK if self is Color.WHITE else Color.WHITE


# 四个成线方向（行、列增量）
DIRECTIONS: tuple[tuple[int, int], ...] = (
    (0, 1),  # 横
    (1, 0),  # 竖
    (1, 1),  # 右下斜
    (1, -1),  # 左下斜
)

# LLM 提示词中棋子的展示字符
COLOR_SYMBOL: dict[int, str] = {1: "1", -1: "2", 0: "0"}
