"""五子棋规则细节（首版不用禁手）。"""

from __future__ import annotations

from app.core.constants import EMPTY

BOARD_SIZE = 15
WIN_LENGTH = 5


def in_bounds(row: int, col: int, size: int = BOARD_SIZE) -> bool:
    """坐标是否在棋盘内。"""
    return 0 <= row < size and 0 <= col < size


def count_line(
    grid: list[list[int]],
    row: int,
    col: int,
    color: int,
    direction: tuple[int, int],
    size: int = BOARD_SIZE,
) -> int:
    """从 (row, col) 出发沿 direction 统计含自身的连续同色数。"""
    dr, dc = direction
    count = 1
    for sign in (1, -1):
        r, c = row + dr * sign, col + dc * sign
        while in_bounds(r, c, size) and grid[r][c] == color:
            count += 1
            r += dr * sign
            c += dc * sign
    return count


def is_winning_move(
    grid: list[list[int]],
    row: int,
    col: int,
    color: int,
    win_length: int = WIN_LENGTH,
    size: int = BOARD_SIZE,
) -> bool:
    """假设 (row, col) 已落 color 子，判断是否成五连（或更长）。"""
    from app.core.constants import DIRECTIONS

    for direction in DIRECTIONS:
        if count_line(grid, row, col, color, direction, size) >= win_length:
            return True
    return False


def neighbor_has_stone(
    grid: list[list[int]],
    row: int,
    col: int,
    distance: int = 2,
    size: int = BOARD_SIZE,
) -> bool:
    """(row, col) 周围 distance 格内是否已有棋子（候选点筛选用）。"""
    for dr in range(-distance, distance + 1):
        for dc in range(-distance, distance + 1):
            if dr == 0 and dc == 0:
                continue
            r, c = row + dr, col + dc
            if in_bounds(r, c, size) and grid[r][c] != EMPTY:
                return True
    return False
