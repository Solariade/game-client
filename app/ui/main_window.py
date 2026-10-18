"""主窗口：装配棋盘画布、设置区、解说面板、状态栏，并编排后台任务。

线程模型：
- 用户点击与所有 UI 更新在主线程；
- AI 搜索、LLM 流式接收在后台线程；
- 结果经 queue.Queue + root.after 回主线程（QueuePoller）。
"""

from __future__ import annotations

import logging
import queue
import tkinter as tk
from tkinter import ttk
from typing import Any

from app.ai.difficulty import Difficulty, depth_of
from app.common.paths import asset
from app.common.threading_utils import QueuePoller, run_in_background
from app.core.base_game import Move
from app.core.constants import EMPTY
from app.core.exceptions import IllegalMoveError
from app.llm.registry import LLMRegistry
from app.llm.suggestion import format_coord
from app.services.commentary_service import CommentaryService
from app.services.game_service import GameService, TurnResult
from app.ui.analysis_panel import AnalysisPanel
from app.ui.boards.gomoku_canvas import GomokuCanvas
from app.ui.controls import ControlsPanel
from app.ui.status_bar import StatusBar
from app.ui.theme import BG

logger = logging.getLogger(__name__)


class MainWindow:
    """组合根：持有全部服务与控件，负责事件流转。"""

    def __init__(
        self,
        root: tk.Tk,
        game_service: GameService,
        commentary_service: CommentaryService,
        llm_registry: LLMRegistry,
    ) -> None:
        self.root = root
        self.service = game_service
        self.commentary = commentary_service
        self.registry = llm_registry

        self.ai_thinking = False
        self._user_result: TurnResult | None = None
        self._comment_seq = 0  # 当前有效解说流编号，递增即作废旧流
        self._suggest_seq = 0  # 当前有效建议编号，用户落子/重开即作废旧建议
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self._poller = QueuePoller(self._queue, poll_ms=60)

        self._setup_window()
        self._build_layout()
        self.service.new_game()
        self.canvas.sync_board(self.service.board)
        self._announce_start()
        self._poller.start(self.root.after, self._consume_event)
        self._maybe_ai_open()

    # ---- 窗口与布局 ----

    def _setup_window(self) -> None:
        self._logo_img: tk.PhotoImage | None = None
        self.root.title("game-client · 五子棋 AI 对弈")
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self._set_icon()

    def _set_icon(self) -> None:
        """左上角窗口图标：优先 assets/logo.ico，缺失时回退 assets/logo.png。"""
        ico = asset("logo.ico")
        if ico.exists():
            try:
                self.root.iconbitmap(str(ico))
                return
            except tk.TclError:  # pragma: no cover - 图标文件损坏时回退 png
                pass
        png = asset("logo.png")
        if png.exists():
            try:
                self._logo_img = tk.PhotoImage(file=str(png))
                self.root.iconphoto(True, self._logo_img)
            except tk.TclError:  # pragma: no cover
                self._logo_img = None

    def _build_layout(self) -> None:
        self.status_bar = StatusBar(self.root)
        self.status_bar.pack(side="bottom", fill="x")

        container = ttk.Frame(self.root, padding=12)
        container.pack(side="top", fill="both", expand=True)

        self.canvas = GomokuCanvas(
            container, board_size=self.service.board.size, on_click=self._on_board_click
        )
        self.canvas.pack(side="left", fill="both", expand=True)
        # Esc / 右键取消预选，避免虚拟棋子留在棋盘上
        self.root.bind("<Escape>", self._on_cancel_preview)
        self.canvas.bind("<Button-3>", self._on_cancel_preview)

        right = ttk.Frame(container, padding=(12, 0, 0, 0))
        right.pack(side="left", fill="both", expand=True)

        # 首项内容空着且为默认：不进行 AI 解说；内部名与展示名都用空串
        models = [("", "")] + [
            (name, self.registry.display_name(name)) for name in self.registry.available
        ]
        self.controls = ControlsPanel(
            right,
            model_names=models,
            on_model_change=self._on_model_change,
            on_difficulty_change=self._on_difficulty_change,
            on_color_change=self._on_color_change,
            on_suggestion_change=self._on_suggestion_change,
            on_restart=self._restart,
        )
        self.controls.pack(fill="x", pady=(0, 10))

        self.panel = AnalysisPanel(right)
        self.panel.pack(fill="both", expand=True)

    # ---- 状态栏 ----

    def _update_turn_status(self) -> None:
        if self.service.game_over:
            return
        move_no = self.service.board.moves_count + 1
        color = "黑" if self.service.user_color == 1 else "白"
        self.status_bar.set_status(f"第 {move_no} 手，轮到你落子，你执{color}棋")
        self.status_bar.start_wait("你")

    def _announce_start(self) -> None:
        side = "你执黑先行" if self.service.user_color == 1 else "AI 执黑先行"
        model = self.service.config.model_name
        if model:
            self.panel.show_info(
                f"对局开始：{side}，解说模型 {self.registry.display_name(model)}。"
            )
        else:
            self.panel.show_info(f"对局开始：{side}，未选择解说模型，不进行 AI 解说。")
        self.status_bar.stop_wait()  # 新对局读秒从 0 开始
        self._update_turn_status()
        # 用户先手且建议开启时，开局即可看到第一手建议
        self._request_suggestion()

    # ---- 用户交互（主线程） ----

    def _on_board_click(self, move: Move) -> None:
        """两次点击落子：第一次点空位放虚拟棋子，第二次点它才真正落子。

        第一次点击后仍可点击其它空位移动虚拟棋子；点击已占用点不会改变预选。
        """
        if self.ai_thinking or self.service.game_over or not self.service.user_turn:
            return
        if self.service.board.grid[move.row][move.col] != EMPTY:
            self.status_bar.set_status("此处已有棋子，请选择空位")
            return

        pending = self.canvas.pending_move
        if pending == move:  # 第二次点击同一虚拟棋子 → 确认落子
            self._confirm_user_move(move)
            return

        # 第一次点击（或改选其它空位）：只画虚拟棋子，不真正落子
        self.canvas.show_pending(move, self.service.user_color)
        if pending is None:
            self.status_bar.set_status(
                f"已预选 {format_coord(move)}：再点一次虚拟棋子确认落子，点其它空位可更换"
            )
        else:
            self.status_bar.set_status(f"已改选 {format_coord(move)}：再点一次虚拟棋子确认落子")

    def _confirm_user_move(self, move: Move) -> None:
        """确认预选落点并进入正常的用户落子 → AI 回合流程。"""
        self.canvas.clear_pending()
        try:
            result = self.service.user_move(move.row, move.col)
        except (IllegalMoveError, RuntimeError) as exc:
            logger.debug("用户非法落子: %s", exc)
            self.status_bar.set_status("此处不能落子，请选择空位")
            return

        self._suggest_seq += 1  # 用户已落子，丢弃在途建议
        self.canvas.sync_board(self.service.board, last_move=result.move)
        if result.game_over:
            self._handle_game_over(result)
            return

        self._start_ai_turn(user_result=result)

    def _on_cancel_preview(self, _event: Any = None) -> None:
        """Esc / 右键取消预选；随后补算一次建议，恢复棋盘提示。"""
        if self.canvas.pending_move is None:
            return
        self.canvas.clear_pending()
        self._update_turn_status()
        self._request_suggestion()

    def _on_model_change(self, name: str) -> None:
        if not name:  # 清空模型：不进行 AI 解说，并作废仍在途的解说流
            self.service.config.model_name = None
            self._comment_seq += 1
            if self.panel.streaming:
                self.panel.end_stream()
            self.panel.show_info("已清空解说模型，不进行 AI 解说。")
            return
        try:
            self.registry.get(name)
        except Exception as exc:  # noqa: BLE001
            self.panel.show_info(f"模型切换失败：{exc}")
            return
        self.service.config.model_name = name
        self.panel.show_info(f"解说模型已切换为 {self.registry.display_name(name)}。")

    def _on_difficulty_change(self, difficulty: Difficulty) -> None:
        self.service.config.difficulty_depth = depth_of(difficulty)
        self.service.config.difficulty_name = difficulty.value
        hint = "，专家模式思考时间较长" if difficulty is Difficulty.EXPERT else ""
        self.panel.show_info(f"难度已切换为 {difficulty.value}{hint}。")

    def _on_suggestion_change(self, enabled: bool) -> None:
        """开关本地落子建议；关闭时清掉棋盘上的虚线棋子。"""
        self.service.config.suggestion_enabled = enabled
        if not enabled:
            self._suggest_seq += 1  # 作废在途建议，避免关闭后又画出来
            self.canvas.clear_hint()
            self.panel.show_info("已关闭落子建议。")
            return
        self.panel.show_info("已开启落子建议。")
        self._request_suggestion()  # 当前若轮到用户，立即补一条

    def _on_color_change(self, user_color: int) -> None:
        """切换执黑方；换边影响先手，直接重开一局。"""
        if self.ai_thinking:
            self.controls.set_user_color(self.service.user_color)
            self.status_bar.set_status("AI 思考中，请稍后再切换执黑方")
            return
        self.service.set_user_color(user_color)
        self._restart()

    def _restart(self) -> None:
        if self.ai_thinking:
            self.status_bar.set_status("AI 思考中，请稍后再重新开局")
            return
        self._user_result = None
        self._comment_seq += 1  # 作废可能仍在途的解说事件，避免写入已清空的面板
        self._suggest_seq += 1  # 作废旧局面的建议
        self.service.new_game()
        self.canvas.sync_board(self.service.board)
        self.panel.clear()
        self._announce_start()
        self._maybe_ai_open()

    def _maybe_ai_open(self) -> None:
        """AI 执黑时，开局由 AI 先落子。"""
        if self.service.game_over or self.service.user_turn:
            return
        self._start_ai_turn(user_result=None)

    # ---- AI 回合（后台线程 + 队列回主线程） ----

    def _start_ai_turn(self, user_result: TurnResult | None) -> None:
        self.ai_thinking = True
        self._user_result = user_result
        self.status_bar.set_status(f"AI 思考中，搜索深度 {self.service.config.difficulty_depth}")
        self.status_bar.start_wait("AI")

        def _work() -> None:
            try:
                ai_result = self.service.take_ai_turn()
            except BaseException as exc:  # noqa: BLE001
                self._queue.put({"type": "ai_error", "error": str(exc)})
                return
            self._queue.put({"type": "ai_move", "result": ai_result})

        run_in_background(_work)

    def _consume_event(self, event: dict[str, Any]) -> None:
        etype = event.get("type")
        if etype == "ai_move":
            self._on_ai_move(event["result"])
        elif etype == "suggestion":
            self._on_suggestion(event)
        elif etype == "chunk":
            if event.get("seq") == self._comment_seq:
                self.panel.append_chunk(event["text"])
        elif etype == "commentary_end":
            if event.get("seq") == self._comment_seq:
                self.panel.end_stream()
                self._on_commentary_end()
        elif etype == "ai_error":
            self.ai_thinking = False
            self.status_bar.stop_wait()
            self.status_bar.set_status("AI 出错，可点击重新开局")
            self.panel.show_info(f"AI 出错：{event['error']}")

    def _on_ai_move(self, result: TurnResult) -> None:
        self.canvas.sync_board(self.service.board, last_move=result.move)
        if result.game_over:
            self._handle_game_over(result)
            return
        self.ai_thinking = False
        self._update_turn_status()
        if self.panel.streaming:
            self.panel.end_stream()  # 收束上一段未完成的流，保持回合顺序
        # 回合标题始终输出：没有解说模型时面板也按回合组织
        if self._user_result is not None:
            self.panel.show_header(f"第 {self.service.board.moves_count // 2} 回合")
        self._start_commentary(result)
        # 建议单独在后台算：AI 棋子先显示，建议算完再补上
        self._request_suggestion()

    def _request_suggestion(self) -> None:
        """按当前难度深度后台计算建议（不阻塞界面，也不依赖 LLM）。"""
        if not self.service.config.suggestion_enabled:
            return
        if self.service.game_over or self.ai_thinking or not self.service.user_turn:
            return
        if self.canvas.pending_move is not None:
            return  # 用户已在预选，不再补建议（避免两个虚拟子互相干扰）
        self._suggest_seq += 1
        seq = self._suggest_seq
        version = self.service.board.moves_count  # 建议对应的局面版本
        depth = self.service.suggestion_depth

        def _work() -> None:
            move = self.service.suggest_for_user(depth=depth)
            self._queue.put({"type": "suggestion", "move": move, "seq": seq, "version": version})

        run_in_background(_work)

    def _on_suggestion(self, event: dict[str, Any]) -> None:
        # 序号或局面已变化（用户抢先落子/重开）→ 建议已过期，直接丢弃
        if event.get("seq") != self._suggest_seq:
            return
        if event.get("version") != self.service.board.moves_count:
            return
        self._show_local_suggestion(event.get("move"))

    def _start_commentary(self, ai_result: TurnResult) -> None:
        """AI 落子后立即异步请求解说（与用户落子无冲突）。"""
        user_result = self._user_result
        if user_result is None:
            return  # 开局首手无对应玩家着法，不解说
        model_name = self.service.config.model_name
        if not model_name:
            return  # 模型为空白：不进行 AI 解说
        self._comment_seq += 1  # 新一段解说开始，作废旧流事件
        seq = self._comment_seq

        try:
            client = self.registry.get(model_name)
        except Exception as exc:  # noqa: BLE001
            # 模型取用失败时不要开启流式段，否则面板会一直停留在 _streaming
            self.panel.show_info(f"解说不可用：{exc}")
            return

        self.panel.begin_stream()  # 段落头已在 _on_ai_move 写出
        self.status_bar.set_status("解说生成中，可继续落子")

        user_move, ai_move = user_result.move, ai_result.move
        user_color = self.service.user_color
        board_snapshot = self.service.board.clone()
        move_db_id = ai_result.move_db_id

        def _on_chunk(text: str) -> None:
            self._queue.put({"type": "chunk", "text": text, "seq": seq})

        def _on_done(full: str) -> None:
            self._queue.put({"type": "commentary_end", "seq": seq, "text": full})

        def _work() -> None:
            self.commentary.generate(
                client,
                board_snapshot,
                user_move,
                ai_move,
                user_color,
                move_id=move_db_id,
                on_chunk=_on_chunk,
                on_done=_on_done,
            )

        run_in_background(_work)

    def _on_commentary_end(self) -> None:
        if not self.service.game_over and not self.ai_thinking:
            self._update_turn_status()

    def _show_local_suggestion(self, move: Move | None) -> None:
        """把本地引擎生成的建议画成虚拟棋子，并在面板显示坐标。

        建议完全不依赖 LLM：模型选「空白」时同样生效。
        """
        if not self.service.config.suggestion_enabled:
            return
        if move is None or self.service.game_over or self.ai_thinking:
            return
        if not self.service.user_turn:
            return
        if self.canvas.pending_move is not None:
            return  # 用户预选期间不覆盖其虚拟棋子
        if self.service.board.grid[move.row][move.col] != EMPTY:
            return
        self.canvas.show_hint(move, self.service.user_color)
        self.panel.show_info(
            f"本地建议：{format_coord(move)}（点一次预选，再点一次虚拟棋子确认落子）"
        )

    def _handle_game_over(self, result: TurnResult) -> None:
        self.ai_thinking = False
        self.status_bar.stop_wait()
        if result.win_line:
            self.canvas.highlight_win(result.win_line)
        if result.winner is None:
            status = "对局结束：平局，棋盘已满"
        elif result.winner == self.service.user_color:
            status = "对局结束：你赢了"
        else:
            status = "对局结束：AI 获胜"
        self.status_bar.set_status(status)
        self.panel.show_info(f"{status}，点击「重新开局」再来一局。")
        logger.info("对局结束展示: winner=%s", result.winner)
