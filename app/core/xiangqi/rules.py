"""象棋规则内核：七兵种走法、将军/将帅对脸检测、合法着法过滤（纯函数）。

棋盘为 10 行 × 9 列的 grid（见 fen.py 坐标约定），红 = 大写 = 1、黑 = 小写 = -1。
合法着法 = 伪走法中「走后己方不被将军且两帅不对脸」的着法。
"""

from __future__ import annotations

from app.core.base_game import Move

ROWS = 10
COLS = 9
RED = 1
BLACK = -1

# 九宫与楚河汉界（红在下半场 row 5~9，黑在上半场 row 0~4）
_PALACE_COLS = range(3, 6)
_RED_PALACE_ROWS = range(7, 10)
_BLACK_PALACE_ROWS = range(0, 3)

# 马的 8 个跳位与对应蹩腿偏移（沿 2 格方向的正交一步）
_KNIGHT_MOVES: tuple[tuple[int, int, int, int], ...] = (
    (-2, -1, -1, 0),
    (-2, 1, -1, 0),
    (2, -1, 1, 0),
    (2, 1, 1, 0),
    (-1, -2, 0, -1),
    (1, -2, 0, -1),
    (-1, 2, 0, 1),
    (1, 2, 0, 1),
)
_ELEPHANT_STEPS = ((-2, -2), (-2, 2), (2, -2), (2, 2))
_DIAG_STEPS = ((-1, -1), (-1, 1), (1, -1), (1, 1))
_ORTHO_STEPS = ((-1, 0), (1, 0), (0, -1), (0, 1))


def in_bounds(r: int, c: int) -> bool:
    return 0 <= r < ROWS and 0 <= c < COLS


def side_of(piece: str) -> int:
    """棋子归属：大写红 = 1，小写黑 = -1。"""
    return RED if piece.isupper() else BLACK


def _in_palace(r: int, c: int, side: int) -> bool:
    if c not in _PALACE_COLS:
        return False
    rows = _RED_PALACE_ROWS if side == RED else _BLACK_PALACE_ROWS
    return r in rows


def _own_half(r: int, side: int) -> bool:
    """是否在本方半场（相的活动界限，不过河）。"""
    return r >= 5 if side == RED else r <= 4


def find_king(grid: list[list[str]], side: int) -> tuple[int, int] | None:
    """找 side 方将/帅的位置；找不到返回 None（异常局面）。"""
    target = "K" if side == RED else "k"
    for r in range(ROWS):
        for c in range(COLS):
            if grid[r][c] == target:
                return r, c
    return None


# ---- 各兵种伪走法（目标为空位或敌子，不考虑送将） ----


def _rook_targets(grid: list[list[str]], r: int, c: int, side: int) -> list[tuple[int, int]]:
    targets = []
    for dr, dc in _ORTHO_STEPS:
        nr, nc = r + dr, c + dc
        while in_bounds(nr, nc):
            piece = grid[nr][nc]
            if piece == "":
                targets.append((nr, nc))
            else:
                if side_of(piece) != side:
                    targets.append((nr, nc))
                break
            nr, nc = nr + dr, nc + dc
    return targets


def _cannon_targets(grid: list[list[str]], r: int, c: int, side: int) -> list[tuple[int, int]]:
    """炮：平移走空位；吃子须隔一个炮架（第一个子之后的首个敌子）。"""
    targets = []
    for dr, dc in _ORTHO_STEPS:
        nr, nc = r + dr, c + dc
        while in_bounds(nr, nc) and grid[nr][nc] == "":  # 阶段一：滑行空位
            targets.append((nr, nc))
            nr, nc = nr + dr, nc + dc
        nr, nc = nr + dr, nc + dc  # 越过炮架
        while in_bounds(nr, nc):  # 阶段二：炮架后首个子，敌则可吃
            piece = grid[nr][nc]
            if piece != "":
                if side_of(piece) != side:
                    targets.append((nr, nc))
                break
            nr, nc = nr + dr, nc + dc
    return targets


def _knight_targets(grid: list[list[str]], r: int, c: int, side: int) -> list[tuple[int, int]]:
    targets = []
    for dr, dc, lr, lc in _KNIGHT_MOVES:
        nr, nc = r + dr, c + dc
        if not in_bounds(nr, nc):
            continue  # 目标界内则蹩腿位（正交一步）必然也界内
        if grid[r + lr][c + lc] != "":
            continue  # 蹩马腿
        if grid[nr][nc] == "" or side_of(grid[nr][nc]) != side:
            targets.append((nr, nc))
    return targets


def _elephant_targets(grid: list[list[str]], r: int, c: int, side: int) -> list[tuple[int, int]]:
    """相/象：田字走位，塞象眼不可走，不能过河。"""
    targets = []
    for dr, dc in _ELEPHANT_STEPS:
        nr, nc = r + dr, c + dc
        if not in_bounds(nr, nc) or not _own_half(nr, side):
            continue
        if grid[r + dr // 2][c + dc // 2] != "":
            continue  # 塞象眼
        if grid[nr][nc] == "" or side_of(grid[nr][nc]) != side:
            targets.append((nr, nc))
    return targets


def _advisor_targets(grid: list[list[str]], r: int, c: int, side: int) -> list[tuple[int, int]]:
    """仕/士：九宫内斜走一步。"""
    targets = []
    for dr, dc in _DIAG_STEPS:
        nr, nc = r + dr, c + dc
        if _in_palace(nr, nc, side) and (grid[nr][nc] == "" or side_of(grid[nr][nc]) != side):
            targets.append((nr, nc))
    return targets


def _king_targets(grid: list[list[str]], r: int, c: int, side: int) -> list[tuple[int, int]]:
    """帅/将：九宫内直走一步。"""
    targets = []
    for dr, dc in _ORTHO_STEPS:
        nr, nc = r + dr, c + dc
        if _in_palace(nr, nc, side) and (grid[nr][nc] == "" or side_of(grid[nr][nc]) != side):
            targets.append((nr, nc))
    return targets


def _pawn_targets(grid: list[list[str]], r: int, c: int, side: int) -> list[tuple[int, int]]:
    """兵/卒：未过河只进；过河（红 row<=4 / 黑 row>=5）后可横走，永不后退。"""
    forward = (-1, 0) if side == RED else (1, 0)
    crossed = r <= 4 if side == RED else r >= 5
    steps = [forward]
    if crossed:
        steps.extend(((0, -1), (0, 1)))
    targets = []
    for dr, dc in steps:
        nr, nc = r + dr, c + dc
        if in_bounds(nr, nc) and (grid[nr][nc] == "" or side_of(grid[nr][nc]) != side):
            targets.append((nr, nc))
    return targets


_PIECE_TARGETS = {
    "R": _rook_targets,
    "C": _cannon_targets,
    "N": _knight_targets,
    "B": _elephant_targets,
    "A": _advisor_targets,
    "K": _king_targets,
    "P": _pawn_targets,
}


def pseudo_moves(grid: list[list[str]], r: int, c: int) -> list[tuple[int, int]]:
    """(r, c) 处棋子的伪走法（不考虑送将/对脸）。"""
    piece = grid[r][c]
    if piece == "":
        return []
    return _PIECE_TARGETS[piece.upper()](grid, r, c, side_of(piece))


# ---- 将军与合法着法 ----


def kings_facing(grid: list[list[str]]) -> bool:
    """两帅是否直接照面（同列且中间无子）。红将在下、黑将在上，按行序扫中间。"""
    rk, bk = find_king(grid, RED), find_king(grid, BLACK)
    if rk is None or bk is None or rk[1] != bk[1]:
        return False
    top, bottom = sorted((rk[0], bk[0]))
    for r in range(top + 1, bottom):
        if grid[r][rk[1]] != "":
            return False
    return True


def is_in_check(grid: list[list[str]], side: int) -> bool:
    """side 方是否被将军（含将帅对脸：对脸视为双方受将，任何致对脸的着法非法）。"""
    king = find_king(grid, side)
    if king is None:
        return True
    return is_attacked(grid, king[0], king[1], -side) or kings_facing(grid)


def is_attacked(grid: list[list[str]], r: int, c: int, by_side: int) -> bool:
    """(r, c) 是否被 by_side 方任一棋子攻击。"""
    for rr in range(ROWS):
        for cc in range(COLS):
            piece = grid[rr][cc]
            if piece != "" and side_of(piece) == by_side and (r, c) in pseudo_moves(grid, rr, cc):
                return True
    return False


def apply_move(grid: list[list[str]], move: Move) -> str:
    """在 grid 上执行着法，返回被吃子（空串表示未吃子）。调用方保证着法合法。"""
    captured = grid[move.to_row or 0][move.to_col or 0]
    grid[move.to_row or 0][move.to_col or 0] = grid[move.row][move.col]
    grid[move.row][move.col] = ""
    return captured


def undo_move(grid: list[list[str]], move: Move, captured: str) -> None:
    """回退 apply_move。"""
    grid[move.row][move.col] = grid[move.to_row or 0][move.to_col or 0]
    grid[move.to_row or 0][move.to_col or 0] = captured


def legal_targets(grid: list[list[str]], r: int, c: int) -> list[tuple[int, int]]:
    """(r, c) 处棋子的合法着法终点（走后不被将军且不对脸）。"""
    piece = grid[r][c]
    if piece == "":
        return []
    side = side_of(piece)
    targets = []
    for tr, tc in pseudo_moves(grid, r, c):
        move = Move(r, c, tr, tc)
        captured = apply_move(grid, move)
        if not is_in_check(grid, side):
            targets.append((tr, tc))
        undo_move(grid, move, captured)
    return targets


def legal_moves(grid: list[list[str]], side: int) -> list[Move]:
    """side 方当前全部合法着法。"""
    moves: list[Move] = []
    for r in range(ROWS):
        for c in range(COLS):
            piece = grid[r][c]
            if piece != "" and side_of(piece) == side:
                moves.extend(Move(r, c, tr, tc) for tr, tc in legal_targets(grid, r, c))
    return moves


def perft(grid: list[list[str]], side: int, depth: int) -> int:
    """逐层合法着法计数（测试基准：起始局面 1/2/3/4 层 = 44/1920/79666/3290240，
    与 Pikafish 实测一致）。"""
    if depth == 0:
        return 1
    total = 0
    for move in legal_moves(grid, side):
        captured = apply_move(grid, move)
        total += perft(grid, -side, depth - 1)
        undo_move(grid, move, captured)
    return total
