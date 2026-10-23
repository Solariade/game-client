"""假 UCI 引擎子进程脚本：仅供单测 spawn，按环境变量模拟 Pikafish 行为。

环境变量：
- FAKE_MODE：normal（默认）| hang（go 后不响应）| crash（每次 go 崩溃）
  | crash_once（首次 go 崩溃，配合 FAKE_STATE_FILE 标记文件，重启后正常）
- FAKE_BESTMOVE：返回的 bestmove（默认 h2e2）
- FAKE_SCORE_CP：info 行的厘兵分（默认 35；设了 FAKE_SCORE_MATE 则忽略）
- FAKE_SCORE_MATE：info 行报 mate N（优先于 cp）
- FAKE_PV：PV 着法序列（默认 "h2e2 h9g7 h0g2"）
- FAKE_GO_DELAY：go 后延迟多少秒再应答（默认 0）
- FAKE_STATE_FILE：crash_once 模式的标记文件路径

思考放在后台线程，主线程持续读命令：hang 模式下收到 quit 也能立即退出，
避免测试 teardown 卡在 quit 超时上。
"""

from __future__ import annotations

import os
import sys
import threading
import time
from pathlib import Path

MODE = os.environ.get("FAKE_MODE", "normal")
BESTMOVE = os.environ.get("FAKE_BESTMOVE", "h2e2")
SCORE_CP = os.environ.get("FAKE_SCORE_CP", "35")
SCORE_MATE = os.environ.get("FAKE_SCORE_MATE", "")
PV = os.environ.get("FAKE_PV", "h2e2 h9g7 h0g2")
GO_DELAY = float(os.environ.get("FAKE_GO_DELAY", "0"))
STATE_FILE = os.environ.get("FAKE_STATE_FILE", "")


def emit(line: str) -> None:
    print(line, flush=True)


def reply_go() -> None:
    if MODE == "hang":
        time.sleep(600)
        return
    if MODE == "crash":
        os._exit(1)
    if MODE == "crash_once" and STATE_FILE:
        marker = Path(STATE_FILE)
        if not marker.exists():
            marker.write_text("crashed", encoding="utf-8")
            os._exit(1)
    time.sleep(GO_DELAY)
    if SCORE_MATE:
        emit(f"info depth 10 score mate {SCORE_MATE} pv {PV}")
    else:
        emit(f"info depth 10 score cp {SCORE_CP} pv {PV}")
    emit(f"bestmove {BESTMOVE}")


def main() -> None:
    for line in sys.stdin:
        cmd = line.strip()
        if not cmd:
            continue
        if cmd == "uci":
            emit("id name fake-uci")
            emit("option name EvalFile type string default pikafish.nnue")
            emit("uciok")
        elif cmd == "isready":
            emit("readyok")
        elif cmd == "quit":
            sys.exit(0)
        elif cmd.startswith("go"):
            threading.Thread(target=reply_go, daemon=True).start()
        # ucinewgame / position / setoption：静默接受


if __name__ == "__main__":
    main()
