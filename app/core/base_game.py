"""棋种抽象基类：隔离五子棋与（未来的）象棋差异。

新增棋种只需实现本接口，服务层与 UI 框架不改。
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass(frozen=True)
class Move:
    """一步棋的坐标（行、列，0 起始）。

    五子棋只用起点 (row, col)；象棋是「起点 → 终点」着法，
    终点写在 to_row / to_col（五子棋恒为 None，互不影响）。
    """

    row: int
    col: int
    to_row: int | None = None  # 象棋终点行；五子棋不使用
    to_col: int | None = None  # 象棋终点列；五子棋不使用


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

    @abstractmethod
    def is_playable(self, move: Move) -> bool:
        """建议着法是否可用（五子棋=空位；象棋=己方子起手且该着合法）。"""

    @property
    @abstractmethod
    def move_history(self) -> list[Move]:
        """已落子序列。"""

    @property
    @abstractmethod
    def moves_count(self) -> int:
        """已落子数（服务层据此推断行棋轮次）。"""

    @property
    @abstractmethod
    def winner(self) -> int | None:
        """胜者棋色；未分出胜负时为 None。"""

    def win_line(self) -> list[Move] | None:
        """取胜连线坐标（供 UI 高亮）；棋种无此概念时返回 None（如象棋）。"""
        return None
