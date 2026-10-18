"""五子棋棋盘状态：15×15 二维数组（0 空 / 1 黑 / -1 白）。"""

from __future__ import annotations

from app.core.base_game import BaseGame, Move
from app.core.constants import DIRECTIONS, EMPTY
from app.core.exceptions import GameOverError, IllegalMoveError
from app.core.gomoku.rules import (
    BOARD_SIZE,
    count_line,
    in_bounds,
    is_winning_move,
    neighbor_has_stone,
)


class GomokuBoard(BaseGame):
    """实现 BaseGame 接口的五子棋盘。"""

    def __init__(self, size: int = BOARD_SIZE) -> None:
        self.size = size
        self.grid: list[list[int]] = [[EMPTY] * size for _ in range(size)]
        self._history: list[tuple[Move, int]] = []
        self._winner: int | None = None

    # ---- BaseGame 接口 ----

    def place(self, move: Move, color: int) -> None:
        """落子；越界/占用/已结束时抛 IllegalMoveError 或 GameOverError。"""
        if self._winner is not None:
            raise GameOverError("对局已结束，不能再落子")
        if not in_bounds(move.row, move.col, self.size):
            raise IllegalMoveError(f"落子越界: ({move.row}, {move.col})")
        if color not in (1, -1):
            raise IllegalMoveError(f"非法棋色: {color}")
        if self.grid[move.row][move.col] != EMPTY:
            raise IllegalMoveError(f"位置已被占用: ({move.row}, {move.col})")
        self.grid[move.row][move.col] = color
        self._history.append((move, color))
        if is_winning_move(self.grid, move.row, move.col, color, size=self.size):
            self._winner = color

    def undo(self) -> Move:
        """撤销最后一步（供搜索回溯），空盘抛 IllegalMoveError。"""
        if not self._history:
            raise IllegalMoveError("棋盘为空，无法撤销")
        move, _color = self._history.pop()
        self.grid[move.row][move.col] = EMPTY
        self._winner = None
        return move

    def check_win(self, move: Move) -> bool:
        """判断 move 位置的落子是否形成五连。"""
        color = self.grid[move.row][move.col]
        if color == EMPTY:
            return False
        return is_winning_move(self.grid, move.row, move.col, color, size=self.size)

    def is_full(self) -> bool:
        return all(cell != EMPTY for row in self.grid for cell in row)

    def clone(self) -> GomokuBoard:
        board = GomokuBoard(self.size)
        board.grid = [row[:] for row in self.grid]
        board._history = list(self._history)
        board._winner = self._winner
        return board

    def to_text(self) -> str:
        """文本化棋盘：黑=1 / 白=2 / 空=0，供 LLM 阅读。

        直接采用与「建议落子」相同的坐标系：列 A~O（顶部）、行 1~15（左侧）。
        格子之间留一个空格，保证每一列与表头字母对齐，模型无需数位或换算索引。
        """
        header = "    " + " ".join(chr(ord("A") + c) for c in range(self.size))
        symbols = {1: "1", -1: "2", EMPTY: "0"}
        lines = [header]
        for r in range(self.size):
            cells = " ".join(symbols[cell] for cell in self.grid[r])
            lines.append(f"{r + 1:>2d}  " + cells)
        return "\n".join(lines)

    def valid_moves(self) -> list[Move]:
        """全部空位（不做邻域过滤，过滤在引擎层）。"""
        return [
            Move(r, c)
            for r in range(self.size)
            for c in range(self.size)
            if self.grid[r][c] == EMPTY
        ]

    def candidate_moves(self, distance: int = 2) -> list[Move]:
        """已有棋子周围 distance 格内的空位；空盘返回中心点。"""
        moves = [
            Move(r, c)
            for r in range(self.size)
            for c in range(self.size)
            if self.grid[r][c] == EMPTY and neighbor_has_stone(self.grid, r, c, distance, self.size)
        ]
        if not moves and not self._history:
            center = self.size // 2
            moves = [Move(center, center)]
        return moves

    @property
    def move_history(self) -> list[Move]:
        return [move for move, _color in self._history]

    def history(self) -> list[tuple[Move, int]]:
        """只读副本：[(move, color), ...]，供 UI 重绘使用。"""
        return list(self._history)

    @property
    def winner(self) -> int | None:
        return self._winner

    @property
    def moves_count(self) -> int:
        return len(self._history)

    def last_move(self) -> tuple[Move, int] | None:
        """最后一步 (move, color)；空盘为 None。"""
        return self._history[-1] if self._history else None

    def win_line(self) -> list[Move] | None:
        """取胜的五连坐标（供 UI 高亮）；未取胜为 None。"""
        if self._winner is None or not self._history:
            return None
        move, color = self._history[-1]
        for dr, dc in DIRECTIONS:
            if count_line(self.grid, move.row, move.col, color, (dr, dc), self.size) >= 5:
                cells = [move]
                for sign in (1, -1):
                    r, c = move.row + dr * sign, move.col + dc * sign
                    while in_bounds(r, c, self.size) and self.grid[r][c] == color:
                        cells.append(Move(r, c))
                        r += dr * sign
                        c += dc * sign
                return cells
        return None
