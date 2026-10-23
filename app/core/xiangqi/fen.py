"""象棋 FEN 与 ICCS 坐标：解析、生成、互转（纯函数）。

坐标与 Pikafish / ICCS 约定一致（已用引擎实测校准）：
- 内部棋盘 ``grid[row][col]``，10 行 × 9 列；
- row 0 是黑方底线（棋盘顶部），row 9 是红方底线（底部）；
- col 0 是 a 线，col 8 是 i 线；
- ICCS 着法如 ``h2e2``：列为字母 a~i，行号 0~9 从红方底线数起，
  即 行 = 9 - rank（``a0`` 是红方左车）；
- FEN 自上而下（row 0 起）记行，大写为红（行棋方记 ``w``）、小写为黑（``b``）。
"""

from __future__ import annotations

from app.core.base_game import Move

START_FEN = "rnbakabnr/9/1c5c1/p1p1p1p1p/9/9/P1P1P1P1P/1C5C1/9/RNBAKABNR w - - 0 1"

_ROWS = 10
_COLS = 9
_PIECE_CHARS = set("rnbakcpRNBAKCP")
_SIDE_CHARS = {"w": 1, "b": -1}


def parse_fen(fen: str) -> tuple[list[list[str]], int]:
    """解析 FEN → (grid, 行棋方)。行数/列数/棋子字符/行棋方非法时抛 ValueError。

    仅要求前两个字段（棋盘 + 行棋方），后面的计数字段缺省容忍。
    """
    fields = fen.split()
    if len(fields) < 2:
        raise ValueError(f"FEN 至少需要棋盘与行棋方两个字段: {fen!r}")
    rows = fields[0].split("/")
    if len(rows) != _ROWS:
        raise ValueError(f"FEN 应有 10 行，实际 {len(rows)} 行: {fen!r}")
    grid: list[list[str]] = []
    for row in rows:
        cells: list[str] = []
        for ch in row:
            if ch.isdigit():
                if ch == "0":
                    raise ValueError(f"FEN 行内出现 0: {row!r}")
                cells.extend([""] * int(ch))
            elif ch in _PIECE_CHARS:
                cells.append(ch)
            else:
                raise ValueError(f"FEN 出现非法字符 {ch!r}: {fen!r}")
        if len(cells) != _COLS:
            raise ValueError(f"FEN 某行应展开为 9 列，实际 {len(cells)}: {row!r}")
        grid.append(cells)
    side = _SIDE_CHARS.get(fields[1])
    if side is None:
        raise ValueError(f"FEN 行棋方应为 w/b，实际 {fields[1]!r}")
    return grid, side


def to_fen(grid: list[list[str]], side: int, halfmove: int = 0, fullmove: int = 1) -> str:
    """grid + 行棋方 → 标准 FEN 字符串。"""
    rows: list[str] = []
    for cells in grid:
        parts: list[str] = []
        empty = 0
        for cell in cells:
            if cell == "":
                empty += 1
            else:
                if empty:
                    parts.append(str(empty))
                    empty = 0
                parts.append(cell)
        if empty:
            parts.append(str(empty))
        rows.append("".join(parts) if parts else "9")
    return f"{'/'.join(rows)} {'w' if side == 1 else 'b'} - - {halfmove} {fullmove}"


def iccs_of(move: Move) -> str:
    """Move → ICCS 着法（如 ``h2e2``）；缺终点或越界抛 ValueError。"""
    if move.to_row is None or move.to_col is None:
        raise ValueError(f"象棋着法需要终点: {move}")
    for r, c in ((move.row, move.col), (move.to_row, move.to_col)):
        if not (0 <= r < _ROWS and 0 <= c < _COLS):
            raise ValueError(f"ICCS 坐标越界: {move}")
    return f"{chr(ord('a') + move.col)}{9 - move.row}{chr(ord('a') + move.to_col)}{9 - move.to_row}"


def move_from_iccs(text: str) -> Move:
    """ICCS 着法（如 ``h2e2``）→ Move；格式非法抛 ValueError。"""
    t = text.strip().lower()
    if (
        len(t) != 4
        or not all("a" <= t[i] <= "i" for i in (0, 2))
        or not t[1].isdigit()
        or not t[3].isdigit()
    ):
        raise ValueError(f"ICCS 着法格式应为如 h2e2，实际 {text!r}")
    return Move(
        row=9 - int(t[1]),
        col=ord(t[0]) - ord("a"),
        to_row=9 - int(t[3]),
        to_col=ord(t[2]) - ord("a"),
    )
