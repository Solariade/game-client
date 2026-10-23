"""UCI 子进程封装：读写线程、超时等待、崩溃检测（不含业务语义）。

线程约定：本类自身不做串行化，多线程使用须由上层加锁（XiangqiEngine 持锁调用）。
Windows 下 ``CREATE_NO_WINDOW`` 避免弹出控制台黑框；``cwd`` 设为 exe 所在目录，
Pikafish 的 EvalFile（NNUE 权重）默认按工作目录解析，与 exe 同目录即可找到。
"""

from __future__ import annotations

import queue
import subprocess
import threading
import time
from pathlib import Path


class UCITimeoutError(RuntimeError):
    """等待 UCI 应答超时。"""


class UCICrashedError(RuntimeError):
    """引擎进程已退出（崩溃或被杀）。"""


_CREATE_NO_WINDOW = 0x08000000 if hasattr(subprocess, "CREATE_NO_WINDOW") else 0


class UCIProcess:
    """一个 UCI 引擎子进程：握手、命令、应答等待、退出清理。"""

    def __init__(
        self,
        exe_path: str | Path,
        args: list[str] | None = None,
        *,
        startup_timeout: float = 10.0,
    ) -> None:
        self.exe_path = Path(exe_path)
        self.option_lines: list[str] = []  # 握手时引擎报告的 option 行
        self._queue: queue.Queue[str] = queue.Queue()
        self._crashed = False
        self._closing = False
        self._proc = subprocess.Popen(  # noqa: S603 - 路径由调用方控制
            [str(self.exe_path), *(args or [])],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            text=True,
            bufsize=1,
            cwd=str(self.exe_path.parent),
            creationflags=_CREATE_NO_WINDOW if _CREATE_NO_WINDOW else 0,
        )
        self._reader = threading.Thread(target=self._read_loop, daemon=True)
        self._reader.start()
        try:
            self.send("uci")
            lines = self._wait_for("uciok", startup_timeout)
            self.option_lines = [ln for ln in lines if ln.startswith("option")]
            # NNUE 权重与 exe 同目录时显式指定绝对路径，避免依赖工作目录
            nnue = next(self.exe_path.parent.glob("*.nnue"), None)
            if nnue is not None:
                self.send(f"setoption name EvalFile value {nnue}")
            self.send("isready")
            self._wait_for("readyok", startup_timeout)
        except BaseException:
            self._kill()
            raise

    # ---- 底层读写 ----

    def _read_loop(self) -> None:
        """后台读线程：持续把引擎输出入队；流关闭视为进程退出。"""
        assert self._proc.stdout is not None
        for line in self._proc.stdout:
            self._queue.put(line.rstrip("\r\n"))
        if not self._closing:
            self._crashed = True

    def send(self, cmd: str) -> None:
        """发送一条命令；进程已死抛 UCICrashedError。"""
        assert self._proc.stdin is not None
        try:
            self._proc.stdin.write(cmd + "\n")
            self._proc.stdin.flush()
        except (BrokenPipeError, OSError) as exc:
            self._crashed = True
            raise UCICrashedError(f"引擎进程写入失败: {exc}") from exc

    def _wait_for(self, token: str, timeout: float) -> list[str]:
        """等待以 token 开头的应答行，返回截至该行（含）的全部输出。"""
        lines: list[str] = []
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                line = self._queue.get(timeout=0.1)
            except queue.Empty:
                if self._crashed:
                    raise UCICrashedError(f"引擎进程在等待 {token} 时退出") from None
                continue
            lines.append(line)
            if line.startswith(token):
                return lines
        raise UCITimeoutError(f"等待 {token} 超时（{timeout:.1f}s）")

    # ---- 业务命令 ----

    @property
    def crashed(self) -> bool:
        return self._crashed

    def go(self, fen: str, movetime_ms: int, timeout: float | None = None) -> tuple[str, list[str]]:
        """对局面思考 movetime_ms 毫秒，返回 (bestmove, 全部输出行)。"""
        self.send(f"position fen {fen}")
        self.send(f"go movetime {movetime_ms}")
        if timeout is None:
            timeout = movetime_ms / 1000 + 5.0
        lines = self._wait_for("bestmove", timeout)
        bestmove = ""
        for line in lines:
            if line.startswith("bestmove"):
                parts = line.split()
                if len(parts) > 1:
                    bestmove = parts[1]
        if not bestmove:
            raise UCITimeoutError("bestmove 应答缺少着法")
        return bestmove, lines

    def new_game(self) -> None:
        """重置引擎内部状态（新对局清置换表）。"""
        self.send("ucinewgame")

    def quit(self) -> None:
        """礼貌退出：发送 quit 并等待，超时强杀。"""
        self._closing = True
        try:
            self.send("quit")
            self._proc.wait(timeout=3)
        except (UCICrashedError, subprocess.TimeoutExpired, OSError):
            self._kill()

    def _kill(self) -> None:
        # 进程可能已自行退出（崩溃路径），kill/wait 都要容忍
        self._closing = True
        try:
            self._proc.kill()
        except OSError:
            pass
        try:
            self._proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
            pass
