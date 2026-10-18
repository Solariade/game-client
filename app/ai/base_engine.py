"""引擎抽象基类：为象棋等后续棋种预留。"""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.core.base_game import BaseGame, Move


class BaseEngine(ABC):
    """棋种无关的走棋引擎接口。"""

    @abstractmethod
    def search(self, game: BaseGame, depth: int, ai_color: int | None = None) -> Move:
        """给定局面与深度，返回引擎选择的落点。

        ai_color 指定为哪一方走棋；None 时由实现自行推断。
        同一接口既用于 AI 走棋，也用于给用户生成本地建议。
        """
