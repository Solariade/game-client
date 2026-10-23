"""象棋棋盘状态：实现 BaseGame 接口（红 = 1 先行，黑 = -1）。

与五子棋同构：颜色仍是 ±1、先手为 1，GameService 的轮次奇偶推断可复用；
着法是「起点 → 终点」（Move.to_row/to_col），胜负为将死或困毙。
"""

from __future__ import annotations

from app.core.base_game import BaseGame, Move
from app.core.exceptions import GameOverError, IllegalMoveError
from app.core.xiangqi import fen, notation, rules

# LLM 文本局面中棋子的汉字对照（红大写 / 黑小写）
PIECE_CN: dict[str, str] = {
    "K": "帅",
    "A": "仕",
    "B": "相",
    "N": "马",
    "R": "车",
    "C": "炮",
    "P": "兵",
    "k": "将",
    "a": "士",
    "b": "象",
    "n": "马",
    "r": "车",
    "c": "炮",
    "p": "卒",
}


class XiangqiBoard(BaseGame):
    """实现 BaseGame 接口的象棋棋盘。"""

    def __init__(self, start_fen: str | None = None) -> None:
        self._start_fen = start_fen or fen.START_FEN
        self.grid, self._side = fen.parse_fen(self._start_fen)
        self._history: list[tuple[Move, int, str]] = []  # (着法, 颜色, 被吃子)
        self._winner: int | None = None
        self._end_reason: str | None = None  # 'checkmate' 将死 / 'stalemate' 困毙

    # ---- BaseGame 接口 ----

    def place(self, move: Move, color: int) -> None:
        """走一着并校验合法性；非法抛 IllegalMoveError，已结束抛 GameOverError。"""
        if self._winner is not None:
            raise GameOverError("对局已结束，不能再走棋")
        if color not in (1, -1):
            raise IllegalMoveError(f"非法棋色: {color}")
        if color != self._side:
            raise IllegalMoveError("没轮到该方走棋")
        if move.to_row is None or move.to_col is None:
            raise IllegalMoveError(f"象棋着法需要起点与终点: {move}")
        tr, tc = move.to_row, move.to_col
        if not rules.in_bounds(move.row, move.col) or not rules.in_bounds(tr, tc):
            raise IllegalMoveError(f"着法越界: {move}")
        piece = self.grid[move.row][move.col]
        if piece == "" or rules.side_of(piece) != color:
            raise IllegalMoveError(f"起点不是本方棋子: {move}")
        if (tr, tc) not in rules.legal_targets(self.grid, move.row, move.col):
            raise IllegalMoveError(f"该着法不合法（被将军/蹩腿/越界等）: {move}")

        captured = rules.apply_move(self.grid, move)
        self._history.append((move, color, captured))
        self._side = -color
        # 对方无任何合法着法即终局：被将军 = 将死，否则 = 困毙（象棋规则同样判负）
        if not rules.legal_moves(self.grid, self._side):
            self._winner = color
            self._end_reason = (
                "checkmate" if rules.is_in_check(self.grid, self._side) else "stalemate"
            )

    def undo(self) -> Move:
        """撤销最后一着（恢复被吃子），空盘抛 IllegalMoveError。"""
        if not self._history:
            raise IllegalMoveError("尚无着法，无法撤销")
        move, color, captured = self._history.pop()
        rules.undo_move(self.grid, move, captured)
        self._side = color
        self._winner = None
        self._end_reason = None
        return move

    def check_win(self, move: Move) -> bool:
        """该着走完后对局是否结束（将死或困毙）。"""
        return self._winner is not None

    def is_full(self) -> bool:
        """象棋无满盘平局，恒为 False（接口兼容）。"""
        return False

    def clone(self) -> XiangqiBoard:
        board = XiangqiBoard()
        board._start_fen = self._start_fen
        board.grid = [row[:] for row in self.grid]
        board._side = self._side
        board._history = list(self._history)
        board._winner = self._winner
        board._end_reason = self._end_reason
        return board

    def to_text(self) -> str:
        """文本化棋盘（供 LLM 阅读）：红大写、黑小写、空位 ``.``。

        行号沿用 ICCS rank（顶部黑方 9 → 底部红方 0），列 a~i，
        与引擎着法（如 h2e2）坐标一致；字母与汉字对照见 ``PIECE_CN``。
        """
        header = "   " + " ".join(chr(ord("a") + c) for c in range(rules.COLS))
        lines = [header]
        for r in range(rules.ROWS):
            cells = " ".join(self.grid[r][c] if self.grid[r][c] else "." for c in range(rules.COLS))
            lines.append(f"{9 - r}  {cells}")
        side_name = "红" if self._side == rules.RED else "黑"
        return "\n".join(lines) + f"\n行棋方：{side_name}"

    def valid_moves(self) -> list[Move]:
        """当前行棋方全部合法着法。"""
        return rules.legal_moves(self.grid, self._side)

    @property
    def move_history(self) -> list[Move]:
        return [move for move, _color, _cap in self._history]

    @property
    def winner(self) -> int | None:
        return self._winner

    # ---- 象棋扩展（UI / 引擎 / 建议用） ----

    def history(self) -> list[tuple[Move, int]]:
        """只读副本：[(着法, 颜色), ...]，供 UI 重绘使用。"""
        return [(move, color) for move, color, _cap in self._history]

    def history_notations(self) -> list[str]:
        """中文记法着法序列（如 ``['炮二平五', '马8进7']``）：从起始局面重演生成。"""
        grid, _side = fen.parse_fen(self._start_fen)
        texts: list[str] = []
        for move, _color, _cap in self._history:
            texts.append(notation.move_text(grid, move))
            rules.apply_move(grid, move)
        return texts

    @property
    def moves_count(self) -> int:
        return len(self._history)

    @property
    def side_to_move(self) -> int:
        """当前行棋方：红 1 / 黑 -1。"""
        return self._side

    @property
    def end_reason(self) -> str | None:
        """终局原因：'checkmate' 将死 / 'stalemate' 困毙 / None 未终局。"""
        return self._end_reason

    def last_move(self) -> tuple[Move, int] | None:
        """最后一着 (着法, 颜色)；空盘为 None。"""
        if not self._history:
            return None
        move, color, _cap = self._history[-1]
        return move, color

    def to_fen(self) -> str:
        """当前局面的标准 FEN（供引擎）。"""
        return fen.to_fen(self.grid, self._side, fullmove=len(self._history) // 2 + 1)

    def is_in_check(self, side: int | None = None) -> bool:
        """side 方是否被将军；缺省为当前行棋方。"""
        return rules.is_in_check(self.grid, self._side if side is None else side)

    def is_playable(self, move: Move) -> bool:
        """建议着法是否可用：起终点界内、起点为本方棋子且该着合法。"""
        if move.to_row is None or move.to_col is None:
            return False
        tr, tc = move.to_row, move.to_col
        if not rules.in_bounds(move.row, move.col) or not rules.in_bounds(tr, tc):
            return False
        piece = self.grid[move.row][move.col]
        if piece == "" or rules.side_of(piece) != self._side:
            return False
        return (tr, tc) in rules.legal_targets(self.grid, move.row, move.col)
