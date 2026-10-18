"""候选走法生成与排序。

- 候选点仅取已有棋子周围 2 格内空位，大幅降低分支因子；
- 按"进攻 + 防守"启发式分值排序，提升 Alpha-Beta 剪枝效率。
"""

from __future__ import annotations

from app.ai.gomoku.evaluator import score_point
from app.core.base_game import Move
from app.core.gomoku.board import GomokuBoard
from app.core.gomoku.rules import BOARD_SIZE


def generate_candidates(
    grid: list[list[int]],
    color: int,
    size: int = BOARD_SIZE,
    distance: int = 2,
    limit: int = 20,
) -> list[Move]:
    """生成按启发式分值降序排列的候选点。

    color 为即将落子的一方；启发分 = 己方进攻分 + 对方进攻分（防守）。
    """
    opp = -color
    scored: list[tuple[int, int, int]] = []  # (score, row, col)
    center = size // 2
    for r in range(size):
        for c in range(size):
            if grid[r][c] != 0:
                continue
            if not _has_neighbor(grid, r, c, distance, size):
                continue
            attack = score_point(grid, r, c, color, size)
            defend = score_point(grid, r, c, opp, size)
            # 中心偏好（微弱），打破平分
            bias = -(abs(r - center) + abs(c - center))
            scored.append((attack + defend, bias, r * size + c))
    if not scored:
        return [Move(center, center)]
    scored.sort(key=lambda t: (t[0], t[1], -t[2]), reverse=True)
    moves = [Move(t[2] // size, t[2] % size) for t in scored[:limit]]
    return moves


def _has_neighbor(grid: list[list[int]], row: int, col: int, distance: int, size: int) -> bool:
    for dr in range(-distance, distance + 1):
        for dc in range(-distance, distance + 1):
            if dr == 0 and dc == 0:
                continue
            r, c = row + dr, col + dc
            if 0 <= r < size and 0 <= c < size and grid[r][c] != 0:
                return True
    return False


def order_moves(board: GomokuBoard, moves: list[Move], color: int) -> list[Move]:
    """对给定走法列表按启发分排序（保留原列表）。"""
    scored = []
    for m in moves:
        s = score_point(board.grid, m.row, m.col, color, board.size)
        scored.append((s, m))
    scored.sort(key=lambda t: t[0], reverse=True)
    return [m for _s, m in scored]
