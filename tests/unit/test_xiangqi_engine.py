"""XiangqiEngine / UCIProcess 单测：全部走 tests/fixtures/fake_uci_engine.py 假引擎。"""

from __future__ import annotations

import sys
import threading
from pathlib import Path

import pytest

from app.ai.xiangqi.engine import (
    EngineError,
    EngineEval,
    EngineUnavailableError,
    XiangqiEngine,
)
from app.ai.xiangqi.uci import UCIProcess
from app.core.base_game import Move
from app.core.xiangqi.board import XiangqiBoard

FAKE_ENGINE = Path(__file__).resolve().parent.parent / "fixtures" / "fake_uci_engine.py"


def make_engine(monkeypatch: pytest.MonkeyPatch, **env: str) -> XiangqiEngine:
    """按环境变量构造指向假引擎的 XiangqiEngine（进程惰性启动，env 先于 spawn 生效）。"""
    for key, value in env.items():
        monkeypatch.setenv(key, value)
    return XiangqiEngine(exe_path=sys.executable, args=[str(FAKE_ENGINE)], timeout_margin=0.5)


@pytest.fixture()
def engine(monkeypatch: pytest.MonkeyPatch) -> XiangqiEngine:
    eng = make_engine(monkeypatch)  # 默认 normal 模式：bestmove h2e2、cp 35
    yield eng
    eng.quit()


def black_to_move_board() -> XiangqiBoard:
    """红方走完炮二平五后的局面（轮黑行棋）。"""
    board = XiangqiBoard()
    board.place(Move(7, 7, 7, 4), color=1)
    return board


class TestUCIProcess:
    def test_handshake_captures_options_and_go(self) -> None:
        proc = UCIProcess(sys.executable, [str(FAKE_ENGINE)])
        try:
            assert any("EvalFile" in ln for ln in proc.option_lines)
            assert not proc.crashed
            bestmove, lines = proc.go(XiangqiBoard().to_fen(), 50)
            assert bestmove == "h2e2"
            assert any(ln.startswith("info") for ln in lines)
        finally:
            proc.quit()


class TestXiangqiEngine:
    def test_unavailable_when_exe_missing(self, tmp_path: Path) -> None:
        eng = XiangqiEngine(exe_path=tmp_path / "nope" / "pikafish.exe")
        assert eng.available is False
        with pytest.raises(EngineUnavailableError):
            eng.search(XiangqiBoard(), depth=3)

    def test_search_returns_fake_bestmove(self, engine: XiangqiEngine) -> None:
        # h2e2 = 炮二平五：起点 (7,7) → 终点 (7,4)
        assert engine.search(XiangqiBoard(), depth=3) == Move(7, 7, 7, 4)

    def test_search_rejects_opponent_piece_move(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 红方行棋时返回黑方马的着法 h9g7 → 非法
        eng = make_engine(monkeypatch, FAKE_BESTMOVE="h9g7")
        with pytest.raises(EngineError, match="非法着法"):
            eng.search(XiangqiBoard(), depth=3)
        eng.quit()

    def test_search_rejects_none_bestmove(self, monkeypatch: pytest.MonkeyPatch) -> None:
        eng = make_engine(monkeypatch, FAKE_BESTMOVE="(none)")
        with pytest.raises(EngineError, match="无着法"):
            eng.search(XiangqiBoard(), depth=3)
        eng.quit()

    def test_analyze_red_view(self, engine: XiangqiEngine) -> None:
        ev = engine.analyze(XiangqiBoard(), 100)
        assert ev.bestmove == "h2e2"
        assert ev.score_cp == 35
        assert ev.mate_in is None
        assert ev.pv == ["h2e2", "h9g7", "h0g2"]

    def test_analyze_records_last_eval(self, engine: XiangqiEngine) -> None:
        """last_eval 供 GameService 在 AI 回合后取用（解说回填）。"""
        assert engine.last_eval is None  # 未分析过
        ev = engine.analyze(black_to_move_board(), 100)
        assert engine.last_eval is ev
        assert engine.last_eval is not None and engine.last_eval.score_cp == -35

    def test_analyze_flips_score_when_black_to_move(self, engine: XiangqiEngine) -> None:
        assert engine.analyze(black_to_move_board(), 100).score_cp == -35

    def test_analyze_mate_signs(self, monkeypatch: pytest.MonkeyPatch) -> None:
        # 假引擎报 mate 3（行棋方视角）：红方行棋 → +3，黑方行棋 → -3
        eng = make_engine(monkeypatch, FAKE_SCORE_MATE="3")
        assert eng.analyze(XiangqiBoard(), 100).mate_in == 3
        assert eng.analyze(black_to_move_board(), 100).mate_in == -3
        eng.quit()

    def test_hang_times_out_to_engine_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        eng = make_engine(monkeypatch, FAKE_MODE="hang")
        with pytest.raises(EngineError) as excinfo:
            eng.analyze(XiangqiBoard(), 100)  # 单轮超时 = 0.1 + 0.5s，两轮 < 2s
        assert not isinstance(excinfo.value, EngineUnavailableError)
        eng.quit()

    def test_crash_raises_after_restart_also_crashes(self, monkeypatch: pytest.MonkeyPatch) -> None:
        eng = make_engine(monkeypatch, FAKE_MODE="crash")
        with pytest.raises(EngineError) as excinfo:
            eng.analyze(XiangqiBoard(), 100)
        assert not isinstance(excinfo.value, EngineUnavailableError)
        eng.quit()

    def test_crash_once_recovers(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
        marker = tmp_path / "crashed.marker"
        eng = make_engine(monkeypatch, FAKE_MODE="crash_once", FAKE_STATE_FILE=str(marker))
        ev = eng.analyze(XiangqiBoard(), 100)
        assert ev.bestmove == "h2e2"
        assert marker.exists()
        eng.quit()

    def test_concurrent_analyze_serialized(self, engine: XiangqiEngine) -> None:
        board = XiangqiBoard()
        results: list[EngineEval | BaseException] = []
        barrier = threading.Barrier(2)

        def worker() -> None:
            barrier.wait(timeout=5)
            try:
                results.append(engine.analyze(board, 100))
            except BaseException as exc:  # noqa: BLE001 - 测试须捕获一切失败
                results.append(exc)

        threads = [threading.Thread(target=worker) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join(timeout=15)
        assert len(results) == 2
        assert all(isinstance(r, EngineEval) for r in results)

    def test_quit_terminates_process(self, engine: XiangqiEngine) -> None:
        engine.analyze(XiangqiBoard(), 100)
        assert engine._proc is not None
        engine.quit()
        assert engine._proc is None
