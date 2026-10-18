"""五子棋棋型评估函数。

对每条线（行/列/两向斜线）构造字符串后按棋型计数：
'1' = 己方子，'0' = 空位，'X' = 对方子或边界（均视为阻挡）。
线两端补 'X'，使边界与阻挡等价。

评分单调递减：五连 > 活四 > 冲四 > 活三 > 眠三 > 活二 > 眠二。
整体评估 = 己方棋型总分 - 对方棋型总分 × 防守权重。
"""

from __future__ import annotations

from app.core.constants import EMPTY
from app.core.gomoku.rules import BOARD_SIZE

# 棋型分值
FIVE = 10_000_000
LIVE_FOUR = 1_000_000
RUSH_FOUR = 100_000
LIVE_THREE = 10_000
SLEEP_THREE = 1_000
LIVE_TWO = 500
SLEEP_TWO = 100

ONE = "1"
ZERO = "0"
BLOCK = "X"

# 各棋型的匹配串（顺序即优先级；先查到高阶棋型即计数）
PATTERNS: list[tuple[str, int]] = [
    # 五连
    ("11111", FIVE),
    # 活四：两边都空
    ("011110", LIVE_FOUR),
    # 冲四：一边被挡的四，或跳四
    ("X11110", RUSH_FOUR),
    ("01111X", RUSH_FOUR),
    ("10111", RUSH_FOUR),
    ("11011", RUSH_FOUR),
    ("11101", RUSH_FOUR),
    # 活三：再走一步可成活四
    ("001110", LIVE_THREE),
    ("011100", LIVE_THREE),
    ("010110", LIVE_THREE),
    ("011010", LIVE_THREE),
    # 眠三：再走一步只能成冲四
    ("X11100", SLEEP_THREE),
    ("00111X", SLEEP_THREE),
    ("X11010", SLEEP_THREE),
    ("01011X", SLEEP_THREE),
    ("X10110", SLEEP_THREE),
    ("01101X", SLEEP_THREE),
    ("X01110", SLEEP_THREE),
    # 活二
    ("001100", LIVE_TWO),
    ("01010", LIVE_TWO),
    ("010010", LIVE_TWO),
    # 眠二
    ("X00110", SLEEP_TWO),
    ("01100X", SLEEP_TWO),
    ("X01010", SLEEP_TWO),
    ("X010010", SLEEP_TWO),
]

# 防守权重：对方棋型略加权，促使 AI 优先防守
DEFENSE_WEIGHT = 1.1


def _line_to_str(line: list[int], color: int) -> str:
    """把一条线的数组转为 pattern 字符串（两端补 X）。"""
    chars = []
    for cell in line:
        if cell == EMPTY:
            chars.append(ZERO)
        elif cell == color:
            chars.append(ONE)
        else:
            chars.append(BLOCK)
    return BLOCK + "".join(chars) + BLOCK


def iter_lines(size: int = BOARD_SIZE) -> list[list[tuple[int, int]]]:
    """生成全部横、竖、斜线坐标序列（长度 >= 5 的才可能成五）。"""
    lines: list[list[tuple[int, int]]] = []
    # 行
    for r in range(size):
        lines.append([(r, c) for c in range(size)])
    # 列
    for c in range(size):
        lines.append([(r, c) for r in range(size)])
    # 主对角线（c - r = k）
    for k in range(-(size - 5), size - 4):
        lines.append([(r, r + k) for r in range(size) if 0 <= r + k < size])
    # 副对角线（c + r = s）
    for s in range(4, 2 * size - 5):
        lines.append([(r, s - r) for r in range(size) if 0 <= s - r < size])
    return [ln for ln in lines if len(ln) >= 5]


_LINE_COORDS_CACHE: dict[int, list[list[tuple[int, int]]]] = {}


def _line_coords(size: int) -> list[list[tuple[int, int]]]:
    if size not in _LINE_COORDS_CACHE:
        _LINE_COORDS_CACHE[size] = iter_lines(size)
    return _LINE_COORDS_CACHE[size]


def score_grid_for_color(grid: list[list[int]], color: int, size: int = BOARD_SIZE) -> int:
    """整盘某色棋型总分（全盘扫描，供评估与测试使用）。"""
    total = 0
    for coords in _line_coords(size):
        line = [grid[r][c] for r, c in coords]
        if all(cell == EMPTY for cell in line):
            continue
        s = _line_to_str(line, color)
        for pattern, score in PATTERNS:
            n = s.count(pattern)
            if n:
                total += n * score
                if score == FIVE:
                    # 已见五连，更高优先级无需继续
                    break
    return total


def evaluate(grid: list[list[int]], ai_color: int, size: int = BOARD_SIZE) -> int:
    """AI 视角整盘评估：己方分 - 对方分 × 防守权重。"""
    opp = -ai_color
    return score_grid_for_color(grid, ai_color, size) - int(
        score_grid_for_color(grid, opp, size) * DEFENSE_WEIGHT
    )


def score_point(
    grid: list[list[int]], row: int, col: int, color: int, size: int = BOARD_SIZE
) -> int:
    """假设 (row, col) 落 color 子后，过该点四条线的棋型分（快速定点启发）。"""
    grid[row][col] = color
    try:
        total = 0
        for dr, dc in ((0, 1), (1, 0), (1, 1), (1, -1)):
            line = []
            r, c = row - dr * 4, col - dc * 4
            for _ in range(9):
                if 0 <= r < size and 0 <= c < size:
                    line.append(grid[r][c])
                r += dr
                c += dc
            s = _line_to_str(line, color)
            found_five = False
            for pattern, score in PATTERNS:
                n = s.count(pattern)
                if n:
                    total += n * score
                    if score == FIVE:
                        found_five = True
                        break
            if found_five:
                # 该点直接成五，无需再看其他线
                return FIVE
        return total
    finally:
        grid[row][col] = EMPTY
