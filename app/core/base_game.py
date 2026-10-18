"""棋种抽象基类：隔离五子棋与（未来的）象棋差异。

新增棋种只需实现本接口，服务层与 UI 框架不改。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Move:
    """一步棋的坐标（行、列，0 起始）。"""

    row: int
    col: int


class BaseGame(ABC):
    """棋种无关的对局状态接口。"""

    @abstractmethod
    def place(self, move: Move, color: int) -> None:
        """落子并校验合法性，非法抛 IllegalMoveError。"""

    @abstractmethod
    def undo(self) -> Move:
        """撤销最后一步并返回之（供搜索回溯）。"""

    @abstractmethod
    def check_win(self, move: Move) -> bool:
        """判定该落子后是否形成胜利。"""

    @abstractmethod
    def is_full(self) -> bool:
        """棋盘是否已满（无空位）。"""

    @abstractmethod
    def clone(self) -> BaseGame:
        """深拷贝当前状态。"""

    @abstractmethod
    def to_text(self) -> str:
        """文本化棋盘（供 LLM 提示词使用）。"""

    @abstractmethod
    def valid_moves(self) -> list[Move]:
        """当前全部合法落点。"""

    @property
    @abstractmethod
    def move_history(self) -> list[Move]:
        """已落子序列。"""

    @property
    @abstractmethod
    def winner(self) -> int | None:
        """胜者棋色；未分出胜负时为 None。"""
