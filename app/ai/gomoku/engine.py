"""五子棋引擎：Minimax + Alpha-Beta 剪枝主流程。

- 直接在棋盘数组上落子/回溯（避免 place/undo 校验开销）；
- 每个节点经 move_ordering 限宽排序候选；
- 根节点先做"一步成五 / 必挡五连"快速路径；
- 胜负分带剩余深度奖励，优先更快的胜利。
"""

from __future__ import annotations

import logging
import time

from app.ai.base_engine import BaseEngine
from app.ai.gomoku.evaluator import (
    DEFENSE_WEIGHT,
    FIVE,
    RUSH_FOUR,
    score_grid_for_color,
)
from app.ai.gomoku.move_ordering import generate_candidates
from app.core.base_game import BaseGame, Move
from app.core.constants import EMPTY
from app.core.gomoku.board import GomokuBoard
from app.core.gomoku.rules import is_winning_move

logger = logging.getLogger(__name__)

WIN = FIVE


class GomokuEngine(BaseEngine):
    """实现 BaseEngine 的五子棋搜索引擎。"""

    def __init__(self, candidate_limit: int = 20) -> None:
        self.candidate_limit = candidate_limit
        self.nodes = 0
        self.last_elapsed: float = 0.0

    def search(self, game: BaseGame, depth: int, ai_color: int | None = None) -> Move:
        """返回 AI 在当前局面的落点。

        ai_color 为 AI 棋色；缺省时按"上一手的对方"推断，空盘视为黑。
        """
        if not isinstance(game, GomokuBoard):
            raise TypeError(f"GomokuEngine 只接受 GomokuBoard，收到 {type(game).__name__}")
        if depth < 1:
            raise ValueError("搜索深度必须 >= 1")

        self.nodes = 0
        start = time.perf_counter()
        size = game.size
        grid = [row[:] for row in game.grid]  # 副本上搜索，不污染对局状态

        if ai_color is None:
            last = game.last_move()
            ai_color = -last[1] if last else 1
        opp = -ai_color

        moves = generate_candidates(grid, ai_color, size, limit=self.candidate_limit)
        if len(moves) == 1:
            self.last_elapsed = time.perf_counter() - start
            return moves[0]

        # 快速路径 1：己方一步成五
        for m in moves:
            grid[m.row][m.col] = ai_color
            win = is_winning_move(grid, m.row, m.col, ai_color, size=size)
            grid[m.row][m.col] = 0
            if win:
                self.last_elapsed = time.perf_counter() - start
                logger.debug("快速路径：一步成五 (%s,%s)", m.row, m.col)
                return m

        # 快速路径 2：对方一步成五，且己方无成五点 → 直接挡
        opp_threats: list[Move] = []
        for m in generate_candidates(grid, opp, size, limit=self.candidate_limit):
            grid[m.row][m.col] = opp
            threat = is_winning_move(grid, m.row, m.col, opp, size=size)
            grid[m.row][m.col] = 0
            if threat:
                opp_threats.append(m)
        if opp_threats:
            self.last_elapsed = time.perf_counter() - start
            logger.debug("快速路径：挡五连 (%s,%s)", opp_threats[0].row, opp_threats[0].col)
            return opp_threats[0]

        # 主搜索
        best_move, best_val = moves[0], float("-inf")
        alpha, beta = float("-inf"), float("inf")
        for m in moves:
            grid[m.row][m.col] = ai_color
            val = -self._negamax(grid, size, opp, depth - 1, -beta, -alpha)
            grid[m.row][m.col] = 0
            if val > best_val:
                best_val, best_move = val, m
                if val > alpha:
                    alpha = val

        self.last_elapsed = time.perf_counter() - start
        logger.debug(
            "搜索完成: depth=%d nodes=%d elapsed=%.3fs best=(%d,%d) score=%.0f",
            depth,
            self.nodes,
            self.last_elapsed,
            best_move.row,
            best_move.col,
            best_val,
        )
        return best_move

    def _has_immediate_win(self, grid: list[list[int]], size: int, color: int) -> bool:
        """轮走方是否已有一步成五的落点（仅用候选点，开销可控）。"""
        for m in generate_candidates(grid, color, size, limit=self.candidate_limit):
            grid[m.row][m.col] = color
            win = is_winning_move(grid, m.row, m.col, color, size=size)
            grid[m.row][m.col] = EMPTY
            if win:
                return True
        return False

    def _negamax(
        self,
        grid: list[list[int]],
        size: int,
        color: int,
        depth: int,
        alpha: float,
        beta: float,
    ) -> float:
        self.nodes += 1
        if depth == 0:
            # negamax 约定：叶子分值取"当前行棋方"视角。
            # 静态评估不区分先后手：双方各有一个四时会被低估，因此轮走方
            # 若能一步成五，必须直接按必胜返回（否则会走出"自己冲四、
            # 却让对手先成五"的漏着）。
            own = score_grid_for_color(grid, color, size)
            if own >= RUSH_FOUR and self._has_immediate_win(grid, size, color):
                return float(WIN)
            opp = score_grid_for_color(grid, -color, size)
            return float(own - int(opp * DEFENSE_WEIGHT))

        moves = generate_candidates(grid, color, size, limit=self.candidate_limit)
        best = float("-inf")
        for m in moves:
            grid[m.row][m.col] = color
            if is_winning_move(grid, m.row, m.col, color, size=size):
                grid[m.row][m.col] = 0
                # 剩余深度越大（越早取胜）分越高
                return float(WIN + depth)
            val = -self._negamax(grid, size, -color, depth - 1, -beta, -alpha)
            grid[m.row][m.col] = 0
            if val > best:
                best = val
                if val > alpha:
                    alpha = val
                    if alpha >= beta:
                        break
        return best
