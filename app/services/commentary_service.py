"""局面→提示词→LLM→解说：流式生成与降级（在后台线程运行）。"""

from __future__ import annotations

import logging
from collections.abc import Callable

from app.core.base_game import Move
from app.core.gomoku.board import GomokuBoard
from app.db.repositories import MoveRepository
from app.llm.base import LLMClient
from app.llm.fallback import fallback_text
from app.llm.prompts import build_gomoku_prompt

logger = logging.getLogger(__name__)


class CommentaryService:
    """组装提示词并流式拉取解说。

    线程约定：generate() 在后台线程执行；
    on_chunk/on_done 回调由调用方保证线程安全（UI 侧经 queue 回主线程）。
    """

    def __init__(self, move_repo: MoveRepository | None = None) -> None:
        self.move_repo = move_repo

    def generate(
        self,
        client: LLMClient,
        board: GomokuBoard,
        user_move: Move,
        ai_move: Move,
        user_color: int,
        move_id: int | None = None,
        on_chunk: Callable[[str], None] | None = None,
        on_done: Callable[[str], None] | None = None,
    ) -> str:
        """流式生成解说并返回全文；异常降级为 fallback 文案。

        解说只负责分析局面；建议落子由本地引擎另行生成，不经过 LLM。
        """
        parts: list[str] = []
        try:
            # 提示词构造也放在 try 内：任何失败都必须走到 on_done，避免面板停在流式状态
            prompt = build_gomoku_prompt(board, user_move, ai_move, user_color)
            for chunk in client.stream_commentary(prompt):
                parts.append(chunk)
                if on_chunk is not None:
                    on_chunk(chunk)
        except BaseException as exc:  # noqa: BLE001 - LLM 故障不阻断对局
            text = fallback_text(exc)
            if on_chunk is not None:
                on_chunk(text)
            parts.append(text)
        full = "".join(parts).strip()
        if on_done is not None:
            on_done(full)
        if move_id is not None and self.move_repo is not None:
            self.move_repo.update_commentary(move_id, full)
        return full
