"""棋种规格：GameService 注入一个 GameSpec 即可工作于五子棋或象棋。

GameSpec 集中棋种差异的「数据侧」（入库格式、界面文案、重建棋盘），
行为侧差异（走法校验、胜负判定）由各棋种的 BaseGame 实现承担；
引擎仍作为独立注入（同一 service 可配任意 BaseEngine），
GameServiceFactory 集中持有各棋种引擎，供 UI 切换棋种时重建服务。
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from app.ai.base_engine import BaseEngine
from app.core.base_game import BaseGame, Move
from app.core.gomoku.board import GomokuBoard
from app.core.gomoku.rules import BOARD_SIZE
from app.core.xiangqi.board import XiangqiBoard
from app.core.xiangqi.fen import iccs_of

if TYPE_CHECKING:
    from app.db.repositories import GameRepository, MoveRepository
    from app.services.game_service import GameService


@dataclass(frozen=True)
class GameSpec:
    """一个棋种的全部注入点。"""

    game_type: str  # games 表 game_type 字段：'gomoku' / 'xiangqi'
    game_factory: Callable[[], BaseGame]  # 新对局重建棋盘
    user_color_name: Callable[[int], str]  # 棋色 → games.user_color（'black'/'red'…）
    position_text: Callable[[Move], str]  # Move → moves.position（'r,c' 或 ICCS 'h2e2'）
    color_display: Callable[[int], str]  # 棋色 → 界面文案（'黑'/'红'…）


def make_gomoku_spec(board_size: int = BOARD_SIZE) -> GameSpec:
    """五子棋规格：1=黑（先手）、-1=白，position 存 '行,列'。"""
    return GameSpec(
        game_type="gomoku",
        game_factory=lambda: GomokuBoard(board_size),
        user_color_name=lambda color: "black" if color == 1 else "white",
        position_text=lambda move: f"{move.row},{move.col}",
        color_display=lambda color: "黑" if color == 1 else "白",
    )


def make_xiangqi_spec() -> GameSpec:
    """象棋规格：1=红（先手）、-1=黑，position 存 ICCS（如 'h2e2'）。"""
    return GameSpec(
        game_type="xiangqi",
        game_factory=XiangqiBoard,
        user_color_name=lambda color: "red" if color == 1 else "black",
        position_text=iccs_of,
        color_display=lambda color: "红" if color == 1 else "黑",
    )


class GameServiceFactory:
    """按棋种组装 GameService（UI 切换棋种用）。

    引擎不进 GameSpec（保持 GameService 注入模型不变），由本工厂集中持有；
    切换时由调用方迁移 config（难度/模型/建议开关）。仓库参数可为 None
    （无持久化的对局，如测试与降级场景）。
    """

    def __init__(
        self,
        engines: dict[str, BaseEngine],
        game_repo: GameRepository | None = None,
        move_repo: MoveRepository | None = None,
    ) -> None:
        self._engines = engines
        self._game_repo = game_repo
        self._move_repo = move_repo
        self._specs = {"gomoku": make_gomoku_spec(), "xiangqi": make_xiangqi_spec()}

    def available_games(self) -> list[str]:
        """当前可玩的棋种（引擎缺失的棋种剔除，如未安装 Pikafish）。"""
        return [
            game_type
            for game_type in self._specs
            if getattr(self._engines.get(game_type), "available", True)
        ]

    @property
    def default_game(self) -> str:
        """启动默认棋种：象棋优先，引擎缺失回落五子棋。"""
        return "xiangqi" if "xiangqi" in self.available_games() else "gomoku"

    def create(self, game_type: str, user_color: int = 1) -> GameService:
        """创建指定棋种的 GameService；未知棋种或引擎不可用抛 ValueError。"""
        from app.services.game_service import GameService  # 局部导入避免循环依赖

        try:
            spec = self._specs[game_type]
        except KeyError:
            raise ValueError(f"未知棋种: {game_type}") from None
        engine = self._engines.get(game_type)
        if engine is None or not getattr(engine, "available", True):
            raise ValueError(f"棋种 {game_type} 的引擎不可用（未安装或启动失败）")
        return GameService(
            engine=engine,
            game_repo=self._game_repo,
            move_repo=self._move_repo,
            user_color=user_color,
            spec=spec,
        )

    def shutdown(self) -> None:
        """退出前关闭所有引擎的子进程（如有；纯计算引擎无此方法则跳过）。"""
        for engine in self._engines.values():
            quit = getattr(engine, "quit", None)
            if callable(quit):
                try:
                    quit()
                except OSError:
                    pass
