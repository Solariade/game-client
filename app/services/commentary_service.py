"""提示词→LLM→解说：流式生成与降级（在后台线程运行）。

棋种无关：只接收组装好的 prompt 字符串，组装函数由 UI 按 game_type 选择
（五子棋 build_gomoku_prompt，象棋 build_xiangqi_prompt）。
"""

from __future__ import annotations

import logging
from collections.abc import Callable

from app.db.repositories import MoveRepository
from app.llm.base import LLMClient
from app.llm.fallback import fallback_text

logger = logging.getLogger(__name__)


class CommentaryService:
    """流式拉取解说并回填。

    线程约定：generate() 在后台线程执行；
    on_chunk/on_done 回调由调用方保证线程安全（UI 侧经 queue 回主线程）。
    """

    def __init__(self, move_repo: MoveRepository | None = None) -> None:
        self.move_repo = move_repo

    def generate(
        self,
        client: LLMClient,
        prompt: str,
        move_id: int | None = None,
        on_chunk: Callable[[str], None] | None = None,
        on_done: Callable[[str], None] | None = None,
    ) -> str:
        """流式生成解说并返回全文；异常降级为 fallback 文案。

        解说只负责分析局面；建议落子由本地引擎另行生成，不经过 LLM。
        """
        parts: list[str] = []
        try:
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
