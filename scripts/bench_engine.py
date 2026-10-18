"""引擎性能基准：各难度思考时间与节点数（开发用脚本）。

用法：
    uv run python scripts/bench_engine.py
"""

import time

from app.ai.difficulty import Difficulty, depth_of
from app.ai.gomoku.engine import GomokuEngine
from app.core.base_game import Move
from app.core.gomoku.board import GomokuBoard


def bench(name: str, board: GomokuBoard, depth: int, ai_color: int = -1) -> None:
    engine = GomokuEngine()
    start = time.perf_counter()
    move = engine.search(board, depth, ai_color=ai_color)
    elapsed = time.perf_counter() - start
    print(
        f"{name:8s} 深度={depth} 落点({move.row},{move.col}) 耗时{elapsed:6.2f}s 节点数{engine.nodes}"
    )


def main() -> None:
    # 场景 1：开局 4 手后的中盘
    b1 = GomokuBoard()
    for mv, color in [((7, 7), 1), ((7, 8), -1), ((8, 8), 1), ((6, 6), -1)]:
        b1.place(Move(*mv), color)

    # 场景 2：10 手后的复杂中盘
    b2 = GomokuBoard()
    for mv, color in [
        ((7, 7), 1),
        ((7, 8), -1),
        ((8, 8), 1),
        ((6, 6), -1),
        ((8, 6), 1),
        ((6, 8), -1),
        ((5, 5), 1),
        ((9, 9), -1),
        ((4, 4), 1),
        ((9, 7), -1),
    ]:
        b2.place(Move(*mv), color)

    print("场景 1（开局 4 手，AI 轮到走）:")
    for d in Difficulty:
        bench(d.value, b1.clone(), depth_of(d))

    print("\n场景 2（10 手中盘，AI 轮到走）:")
    for d in Difficulty:
        bench(d.value, b2.clone(), depth_of(d))


if __name__ == "__main__":
    main()
