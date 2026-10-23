"""初始化：配置、日志、DB、LLM 客户端、服务装配。"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path

from app.ai.difficulty import DEFAULT_DIFFICULTY, depth_of
from app.ai.gomoku.engine import GomokuEngine
from app.ai.xiangqi.engine import XiangqiEngine
from app.common.logging import setup_logging
from app.common.paths import _base_dir
from app.db.connection import connect
from app.db.repositories import GameRepository, MoveRepository
from app.llm.registry import LLMRegistry
from app.services.commentary_service import CommentaryService
from app.services.game_service import GameService
from app.services.game_spec import GameServiceFactory
from app.settings import Settings, load_settings


@dataclass
class AppContext:
    """装配完成的依赖集合。"""

    settings: Settings
    game_service: GameService
    commentary_service: CommentaryService
    llm_registry: LLMRegistry
    # 棋种切换工厂（含各棋种引擎）；None 表示不支持切换（旧用法/测试）
    game_factory: GameServiceFactory | None = field(default=None)


def bootstrap() -> AppContext:
    """按序初始化各层，任何一步失败直接抛出（main 捕获后退出）。"""
    settings = load_settings()
    setup_logging(settings.LOG_LEVEL)
    logger = logging.getLogger(__name__)
    logger.info(
        "game-client 启动: env预设模型=%s 日志级别=%s", settings.DEFAULT_LLM, settings.LOG_LEVEL
    )

    if settings.DB_PATH and not settings.DB_PATH.startswith("runtime/"):
        conn = connect(settings.DB_PATH)
    else:
        # "runtime/..." 相对路径统一挂到 exe/项目根 下的 runtime/
        conn = connect(_base_dir() / settings.DB_PATH)

    game_repo = GameRepository(conn)
    move_repo = MoveRepository(conn)

    registry = LLMRegistry(settings)
    if settings.DEFAULT_LLM not in registry.available:
        # 没有可用解说模型不算错误：本地对弈与建议照常工作
        logger.warning(
            "默认模型 %s 未配置 Key（或缺少模型名），本次运行不进行 AI 解说",
            settings.DEFAULT_LLM,
        )

    xq_exe = Path(settings.XIANGQI_ENGINE_PATH) if settings.XIANGQI_ENGINE_PATH else None
    xiangqi_engine = XiangqiEngine(exe_path=xq_exe)
    if not xiangqi_engine.available:
        # 引擎文件缺失只影响象棋模式：五子棋照常，UI 会隐藏象棋入口
        logger.warning(
            "Pikafish 引擎未找到（%s），象棋模式不可用",
            xq_exe if xq_exe is not None else "assets/engines/pikafish.exe",
        )

    factory = GameServiceFactory(
        engines={"gomoku": GomokuEngine(), "xiangqi": xiangqi_engine},
        game_repo=game_repo,
        move_repo=move_repo,
    )
    game_service = factory.create(factory.default_game, user_color=1)
    game_service.config.difficulty_depth = depth_of(DEFAULT_DIFFICULTY)
    game_service.config.difficulty_name = DEFAULT_DIFFICULTY.value
    # model_name 保持 None：UI 模型下拉默认「空白」（不进行 AI 解说）

    commentary_service = CommentaryService(move_repo=move_repo)

    return AppContext(
        settings=settings,
        game_service=game_service,
        commentary_service=commentary_service,
        llm_registry=registry,
        game_factory=factory,
    )
