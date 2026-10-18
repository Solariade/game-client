"""轮次管理、用户/AI 走棋编排（棋种无关：注入 BaseGame / BaseEngine）。

本服务为纯逻辑、无线程代码：
- 用户走棋 ``user_move`` 在主线程同步执行（含校验、落子、入库、胜负判定）；
- AI 走棋 ``take_ai_turn`` 由 UI 放入后台线程执行，返回 TurnResult；
- 解说由 commentary_service 另行异步处理。
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.ai.base_engine import BaseEngine
from app.core.base_game import Move
from app.core.constants import EMPTY, Color
from app.core.gomoku.board import GomokuBoard
from app.core.gomoku.rules import BOARD_SIZE
from app.db.repositories import GameRepository, MoveRepository

logger = logging.getLogger(__name__)

# 建议搜索深度上限：深度 5 在复杂中局约需 7~15 秒，专家难度下接受这个等待
MAX_SUGGESTION_DEPTH = 5
# 建议比 AI 难度高一层，跟随建议才真正有胜算；专家（5）已到上限，保持同深度
SUGGESTION_DEPTH_BONUS = 1


@dataclass
class TurnResult:
    """一步棋的结果快照。"""

    move: Move
    color: int
    game_over: bool
    winner: int | None = None  # 1 黑 / -1 白 / None 未分胜负
    win_line: list[Move] | None = None
    move_db_id: int | None = None  # moves 表记录 id（解说回填用）


@dataclass
class GameConfig:
    difficulty_depth: int = 3
    model_name: str | None = None
    difficulty_name: str | None = None
    suggestion_enabled: bool = True  # 是否给用户显示本地落子建议


class GameService:
    """一局对局的编排状态机。"""

    def __init__(
        self,
        board: GomokuBoard | None = None,
        engine: BaseEngine | None = None,
        game_repo: GameRepository | None = None,
        move_repo: MoveRepository | None = None,
        user_color: int = Color.BLACK,
        board_size: int = BOARD_SIZE,
    ) -> None:
        self.board = board or GomokuBoard(board_size)
        self.engine = engine
        self.game_repo = game_repo
        self.move_repo = move_repo
        self.user_color = user_color
        self.ai_color = -user_color
        self.config = GameConfig()
        self.game_id: int | None = None
        self.game_over = False
        self.winner: int | None = None

    # ---- 对局生命周期 ----

    def new_game(self) -> None:
        """重开一局：清空棋盘并新建 games 记录。"""
        self.board = GomokuBoard(self.board.size)
        self.game_over = False
        self.winner = None
        if self.game_repo is not None:
            self.game_id = self.game_repo.create_game(
                game_type="gomoku",
                model_name=self.config.model_name,
                difficulty=self.config.difficulty_name,
                user_color="black" if self.user_color == Color.BLACK else "white",
            )
        logger.info(
            "新对局开始: game_id=%s user=%s depth=%d",
            self.game_id,
            "黑" if self.user_color == Color.BLACK else "白",
            self.config.difficulty_depth,
        )

    # ---- 走棋 ----

    def set_user_color(self, color: int) -> None:
        """更新用户棋色（AI 取反）。

        轮次由棋色与已落子数推断，对局中换边会造成轮次错乱，
        调用方应随即 new_game() 重开。
        """
        if color not in (1, -1):
            raise ValueError(f"非法棋色: {color}")
        self.user_color = color
        self.ai_color = -color

    @property
    def user_turn(self) -> bool:
        """当前是否轮到用户（无胜负且落子数为偶数时用户先手）。"""
        if self.game_over:
            return False
        return self.board.moves_count % 2 == (0 if self.user_color == Color.BLACK else 1)

    def user_move(self, row: int, col: int) -> TurnResult:
        """用户落子（主线程同步）。非法落子抛 IllegalMoveError/GameOverError。"""
        move = Move(row, col)
        self.board.place(move, self.user_color)
        return self._finish_turn(move, self.user_color, "user")

    def take_ai_turn(self) -> TurnResult:
        """AI 走棋（后台线程执行）：搜索 → 落子 → 入库 → 胜负判定。"""
        if self.game_over:
            raise RuntimeError("对局已结束")
        if self.engine is None:
            raise RuntimeError("未注入引擎")
        move = self.engine.search(self.board, self.config.difficulty_depth, ai_color=self.ai_color)
        self.board.place(move, self.ai_color)
        return self._finish_turn(move, self.ai_color, "ai")

    @property
    def suggestion_depth(self) -> int:
        """建议搜索深度：比当前 AI 难度高一层（封顶 5 层）。

        简单/中等/困难均比 AI 深一层；专家（5 层）已到上限，保持同深度。
        """
        depth = self.config.difficulty_depth + SUGGESTION_DEPTH_BONUS
        return max(1, min(depth, MAX_SUGGESTION_DEPTH))

    def suggest_for_user(self, depth: int | None = None) -> Move | None:
        """给用户生成一个本地建议落点（完全由引擎产生，不依赖 LLM）。

        depth 缺省取 suggestion_depth（当前难度 +1，封顶 5）。
        搜索在棋盘快照上进行，可与用户随后的落子并发执行。
        对局结束、不轮到用户或结果异常时返回 None。
        """
        if self.game_over or not self.user_turn or self.engine is None:
            return None
        if depth is None:
            depth = self.suggestion_depth
        depth = max(1, min(depth, MAX_SUGGESTION_DEPTH))
        snapshot = self.board.clone()
        try:
            move = self.engine.search(snapshot, depth, ai_color=self.user_color)
        except Exception:  # noqa: BLE001 - 建议失败不应影响对局
            logger.exception("本地建议生成失败")
            return None
        if snapshot.grid[move.row][move.col] != EMPTY:
            return None
        return move

    def _finish_turn(self, move: Move, color: int, player: str) -> TurnResult:
        winner = self.board.winner
        game_over = winner is not None or self.board.is_full()
        if game_over:
            self.game_over = True
            self.winner = winner
            if self.game_repo is not None and self.game_id is not None:
                result = (
                    "draw"
                    if winner is None
                    else ("user_win" if winner == self.user_color else "ai_win")
                )
                self.game_repo.finish_game(self.game_id, result)
            logger.info(
                "对局结束: game_id=%s result=%s",
                self.game_id,
                "平局" if winner is None else ("用户胜" if winner == self.user_color else "AI 胜"),
            )
        move_db_id: int | None = None
        if self.move_repo is not None and self.game_id is not None:
            move_db_id = self.move_repo.add_move(
                self.game_id,
                move_number=self.board.moves_count,
                player=player,
                row=move.row,
                col=move.col,
            )
        return TurnResult(
            move=move,
            color=color,
            game_over=game_over,
            winner=winner,
            win_line=self.board.win_line(),
            move_db_id=move_db_id,
        )
