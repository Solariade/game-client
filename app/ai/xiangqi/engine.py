"""XiangqiEngine：Pikafish 高层封装，实现 BaseEngine 接口。

- 引擎发现：构造参数 > ``assets/engines/pikafish.exe``；不存在时 ``available`` 为 False；
- 惰性启动：首次 ``search``/``analyze`` 才拉起子进程，纯五子棋用户零开销；
- 崩溃恢复：命令失败先关进程重启一次，再失败抛 ``EngineError``；
- 单实例 + 锁：AI 回合线程与建议线程共用，UCI 命令串行；
- 评分统一换算为红方视角（正红优、负黑优），mate_in 带符号（正 = 红方杀）。
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path

from app.ai.base_engine import BaseEngine
from app.ai.xiangqi.uci import UCICrashedError, UCIProcess, UCITimeoutError
from app.common.paths import asset
from app.core.base_game import BaseGame, Move
from app.core.xiangqi import rules
from app.core.xiangqi.board import XiangqiBoard
from app.core.xiangqi.fen import move_from_iccs

logger = logging.getLogger(__name__)

# 难度档（复用五子棋深度语义 2~5）→ 引擎思考时长
DEPTH_TO_MOVETIME_MS: dict[int, int] = {
    2: 300,
    3: 800,
    4: 1500,
    5: 3000,
}
DEFAULT_MOVETIME_MS = 800


class EngineError(RuntimeError):
    """引擎运行失败（无响应、反复崩溃、返回非法着法等）。"""


class EngineUnavailableError(EngineError):
    """引擎可执行文件不存在（象棋模式不可用）。"""


@dataclass(frozen=True)
class EngineEval:
    """一次引擎分析结果（评分均为红方视角）。"""

    bestmove: str  # ICCS 着法，如 "h2e2"
    score_cp: int = 0  # 厘兵；mate 时为 0
    mate_in: int | None = None  # 带符号步数：正 = 红方 N 步杀，负 = 黑方 N 步杀
    pv: list[str] = field(default_factory=list)  # 主要变例（ICCS 序列）


class XiangqiEngine(BaseEngine):
    """Pikafish UCI 引擎的 BaseEngine 实现。"""

    def __init__(
        self,
        exe_path: str | Path | None = None,
        args: list[str] | None = None,
        *,
        timeout_margin: float = 5.0,
    ) -> None:
        """``args``：传给引擎进程的附加命令行参数（测试用假引擎走 ``python script``）。"""
        self._exe = Path(exe_path) if exe_path is not None else asset("engines", "pikafish.exe")
        self._args = args
        self._timeout_margin = timeout_margin
        self._proc: UCIProcess | None = None
        self._lock = threading.Lock()
        self.last_eval: EngineEval | None = None  # 最近一次 analyze 的结果（解说回填用）

    @property
    def available(self) -> bool:
        """引擎是否已安装（只查文件存在，不启动进程）。"""
        return self._exe.exists()

    # ---- BaseEngine 接口 ----

    def search(self, game: BaseGame, depth: int, ai_color: int | None = None) -> Move:
        """按难度档（depth → movetime）走棋，返回合法着法。"""
        if not isinstance(game, XiangqiBoard):
            raise EngineError("XiangqiEngine 仅支持象棋局面")
        movetime = DEPTH_TO_MOVETIME_MS.get(depth, DEFAULT_MOVETIME_MS)
        result = self.analyze(game, movetime)
        try:
            move = move_from_iccs(result.bestmove)
        except ValueError as exc:
            raise EngineError(f"引擎返回无法解析的着法: {result.bestmove}") from exc
        if not game.is_playable(move):
            raise EngineError(f"引擎返回非法着法: {result.bestmove}")
        return move

    # ---- 分析（解说 / 建议共用） ----

    def analyze(self, game: XiangqiBoard, movetime_ms: int) -> EngineEval:
        """对当前局面分析 movetime_ms 毫秒。线程安全（内部串行）。

        结果同时记到 ``last_eval``，供 GameService 在 AI 回合后取用
        （同一把锁串行，读方与 search 同线程，无竞争窗口）。
        """
        fen = game.to_fen()
        side = game.side_to_move
        with self._lock:
            bestmove, lines = self._go_with_restart(fen, movetime_ms)
        result = _parse_eval(bestmove, lines, side)
        self.last_eval = result
        return result

    def new_game(self) -> None:
        """新对局：清空引擎置换表（进程未启动时为空操作）。"""
        with self._lock:
            if self._proc is not None and not self._proc.crashed:
                try:
                    self._proc.new_game()
                except UCICrashedError:
                    self._close_quietly()

    def quit(self) -> None:
        """应用退出时调用：结束引擎进程。"""
        with self._lock:
            if self._proc is not None:
                self._proc.quit()
                self._proc = None

    # ---- 内部：进程生命周期 ----

    def _go_with_restart(self, fen: str, movetime_ms: int) -> tuple[str, list[str]]:
        """执行 go；失败关进程重启一次，再失败抛 EngineError。"""
        last_exc: Exception | None = None
        for attempt in (1, 2):
            proc = self._proc
            if proc is None or proc.crashed:
                try:
                    proc = self._start()
                except (OSError, UCITimeoutError, UCICrashedError) as exc:
                    last_exc = exc
                    logger.warning("引擎启动失败(第 %d 次): %s", attempt, exc)
                    continue
            try:
                return proc.go(fen, movetime_ms, timeout=movetime_ms / 1000 + self._timeout_margin)
            except (UCITimeoutError, UCICrashedError) as exc:
                last_exc = exc
                logger.warning("引擎应答失败(第 %d 次): %s", attempt, exc)
                self._close_quietly()
        raise EngineError(f"引擎不可用: {last_exc}")

    def _start(self) -> UCIProcess:
        if not self.available:
            raise EngineUnavailableError(f"未找到引擎: {self._exe}")
        logger.info("启动引擎: %s", self._exe)
        self._proc = UCIProcess(self._exe, self._args)
        return self._proc

    def _close_quietly(self) -> None:
        if self._proc is not None:
            try:
                self._proc.quit()
            except OSError:
                pass
            self._proc = None


def _parse_eval(bestmove: str, lines: list[str], side: int) -> EngineEval:
    """解析 UCI 输出：取最后一条带 pv 的常规 info 行（跳过上下界估计）。"""
    if bestmove in ("(none)", "none", "0000"):
        raise EngineError("引擎无着法可走（局面已终局？）")
    score_cp, mate_raw, pv = 0, None, []
    for line in lines:
        if not line.startswith("info") or " pv " not in line:
            continue
        parts = line.split()
        if "lowerbound" in parts or "upperbound" in parts:
            continue
        if "score" in parts:
            i = parts.index("score")
            if i + 2 < len(parts) and parts[i + 1] == "cp":
                score_cp, mate_raw = int(parts[i + 2]), None
            elif i + 2 < len(parts) and parts[i + 1] == "mate":
                mate_raw, score_cp = int(parts[i + 2]), 0
        pv = parts[parts.index("pv") + 1 :]
    if mate_raw is None:
        return EngineEval(bestmove=bestmove, score_cp=_to_red_view(score_cp, side), pv=pv)
    # UCI 的 mate 步数是行棋方视角，换算为红方视角的带符号步数
    mate = mate_raw if side == rules.RED else -mate_raw
    return EngineEval(bestmove=bestmove, mate_in=mate, pv=pv)


def _to_red_view(score_cp: int, side: int) -> int:
    """厘兵分从行棋方视角换算为红方视角。"""
    return score_cp if side == rules.RED else -score_cp
