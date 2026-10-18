"""难度→搜索深度映射（棋种无关的档位定义）。"""

from __future__ import annotations

from enum import Enum


class Difficulty(Enum):
    EASY = "简单"
    MEDIUM = "中等"
    HARD = "困难"
    EXPERT = "专家"


# 难度→Minimax 深度
DIFFICULTY_DEPTH: dict[Difficulty, int] = {
    Difficulty.EASY: 2,
    Difficulty.MEDIUM: 3,
    Difficulty.HARD: 4,
    Difficulty.EXPERT: 5,
}

DEFAULT_DIFFICULTY = Difficulty.MEDIUM


def depth_of(difficulty: Difficulty) -> int:
    return DIFFICULTY_DEPTH[difficulty]
