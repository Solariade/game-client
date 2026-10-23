"""主窗口：装配棋盘画布、设置区、解说面板、状态栏，并编排后台任务。

线程模型：
- 用户点击与所有 UI 更新在主线程；
- AI 搜索、LLM 流式接收在后台线程；
- 结果经 queue.Queue + root.after 回主线程（QueuePoller）。

棋种切换（M14）：经 GameServiceFactory 重建 GameService 与画布；
选子状态（象棋）由本类持有，画布只负责渲染。
"""

from __future__ import annotations

import logging
import queue
import tkinter as tk
from tkinter import ttk
from typing import Any

from app.ai.difficulty import Difficulty, depth_of
from app.ai.xiangqi.engine import DEFAULT_MOVETIME_MS, DEPTH_TO_MOVETIME_MS
from app.common.paths import asset
from app.common.threading_utils import QueuePoller, run_in_background
from app.core.base_game import Move
from app.core.constants import EMPTY
from app.core.exceptions import IllegalMoveError
from app.core.gomoku.board import GomokuBoard
from app.core.xiangqi import notation, rules
from app.core.xiangqi.board import PIECE_CN, XiangqiBoard
from app.llm.prompts import (
    build_gomoku_prompt,
    build_xiangqi_prompt,
    score_brief,
    score_display,
)
from app.llm.registry import LLMRegistry
from app.llm.suggestion import format_coord
from app.services.commentary_service import CommentaryService
from app.services.game_service import GameService, TurnResult
from app.services.game_spec import GameServiceFactory
from app.ui.analysis_panel import AnalysisPanel
from app.ui.boards.gomoku_canvas import GomokuCanvas
from app.ui.boards.xiangqi_canvas import XiangqiCanvas
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
        service_factory: GameServiceFactory | None = None,
        xiangqi_virtual_piece: bool = False,
    ) -> None:
        self.root = root
        self.service = game_service
        self.commentary = commentary_service
        self.registry = llm_registry
        self._factory = service_factory
        # 象棋虚拟棋子（配置 XIANGQI_VIRTUAL_PIECE，默认关闭 = 点落点直接走子）
        self._xq_virtual_piece = xiangqi_virtual_piece

        self.ai_thinking = False
        self._user_result: TurnResult | None = None
        self._comment_seq = 0  # 当前有效解说流编号，递增即作废旧流
        self._suggest_seq = 0  # 当前有效建议编号，用户落子/重开即作废旧建议
        self._xq_selection: Move | None = None  # 象棋当前选中的己方棋子
        self._queue: queue.Queue[dict[str, Any]] = queue.Queue()
        self._poller = QueuePoller(self._queue, poll_ms=60)

        self._setup_window()
        self._build_layout()
        self.service.new_game()
        self._sync_canvas()
        self._announce_start()
        self._poller.start(self.root.after, self._consume_event)
        self._maybe_ai_open()
        self._refresh_undo_button()

    @property
    def board(self) -> GomokuBoard:
        """当前五子棋棋盘（五子棋分支内使用）。"""
        assert isinstance(self.service.board, GomokuBoard)
        return self.service.board

    @property
    def xiangqi_board(self) -> XiangqiBoard:
        """当前象棋棋盘（象棋分支内使用）。"""
        assert isinstance(self.service.board, XiangqiBoard)
        return self.service.board

    @property
    def xq_canvas(self) -> XiangqiCanvas:
        """当前象棋画布（象棋分支内使用）。"""
        assert isinstance(self.canvas, XiangqiCanvas)
        return self.canvas

    @property
    def go_canvas(self) -> GomokuCanvas:
        """当前五子棋画布（五子棋分支内使用）。"""
        assert isinstance(self.canvas, GomokuCanvas)
        return self.canvas

    def _is_xiangqi(self) -> bool:
        return self.service.spec.game_type == "xiangqi"

    # ---- 窗口与布局 ----

    def _game_title(self) -> str:
        name = "象棋" if self._is_xiangqi() else "五子棋"
        return f"game-client · {name} AI 对弈"

    def _setup_window(self) -> None:
        self._logo_img: tk.PhotoImage | None = None
        self.root.title(self._game_title())
        self.root.configure(bg=BG)
        self.root.resizable(False, False)
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)
        self._set_icon()

    def _on_close(self) -> None:
        """关窗前停掉引擎子进程（Pikafish 不会随主进程自动退出）。"""
        try:
            if self._factory is not None:
                self._factory.shutdown()
            else:
                quit = getattr(self.service.engine, "quit", None)
                if callable(quit):
                    quit()
        finally:
            self.root.destroy()

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
        self._canvas_master = container

        # 右侧面板先创建；画布随后以 before= 插到它前面——
        # 保证切换棋种重建画布时，画布仍排在面板左侧（pack 按入列顺序分配）
        self._side_panel = ttk.Frame(container, padding=(12, 0, 0, 0))
        self._side_panel.pack(side="left", fill="both", expand=True)

        self.canvas = self._build_canvas()
        self._pack_canvas()
        # Esc / 右键取消预选/选子，避免虚拟棋子留在棋盘上；Ctrl+Z 悔棋
        self.root.bind("<Escape>", self._on_cancel_preview)
        self.root.bind("<Control-z>", self._on_undo_shortcut)
        self.canvas.bind("<Button-3>", self._on_cancel_preview)

        # 首项内容空着且为默认：不进行 AI 解说；内部名与展示名都用空串
        models = [("", "")] + [
            (name, self.registry.display_name(name)) for name in self.registry.available
        ]
        games: list[tuple[str, str]] = [("gomoku", "五子棋")]
        if self._factory is not None and "xiangqi" in self._factory.available_games():
            games.append(("xiangqi", "象棋"))
        self.controls = ControlsPanel(
            self._side_panel,
            model_names=models,
            on_model_change=self._on_model_change,
            on_difficulty_change=self._on_difficulty_change,
            on_color_change=self._on_color_change,
            on_suggestion_change=self._on_suggestion_change,
            on_restart=self._restart,
            game_options=games,
            on_game_change=self._on_game_change if len(games) > 1 else None,
            on_undo=self._undo,
        )
        # 初始下拉与执子格跟随当前棋种（bootstrap 默认可能是象棋）
        # apply_game 只改文案、不改变先后手，再按 service 的真实棋色校正一次
        self.controls.set_game(self.service.spec.game_type)
        self.controls.apply_game(self.service.spec.game_type)
        self.controls.set_user_color(self.service.user_color)
        self.controls.pack(fill="x", pady=(0, 10))

        self.panel = AnalysisPanel(self._side_panel)
        self.panel.pack(fill="both", expand=True)

    def _pack_canvas(self) -> None:
        """画布固定排在右侧面板之前（左侧）。"""
        self.canvas.pack(side="left", fill="both", expand=True, before=self._side_panel)

    def _build_canvas(self) -> GomokuCanvas | XiangqiCanvas:
        if self._is_xiangqi():
            # 执黑时翻转棋盘，让己方棋子始终位于下方（玩家面前）
            return XiangqiCanvas(
                self._canvas_master,
                on_click=self._on_board_click,
                flipped=self.service.user_color != 1,
            )
        return GomokuCanvas(
            self._canvas_master, board_size=self.board.size, on_click=self._on_board_click
        )

    def _sync_canvas(self, last_move: Move | None = None) -> None:
        """按当前棋盘类型整盘重绘画布，并刷新象棋的将军标记。"""
        board = self.service.board
        if isinstance(self.canvas, XiangqiCanvas) and isinstance(board, XiangqiBoard):
            # 换边（执红/执黑切换）后视角跟随执子方，己方在下方
            self.canvas.set_flipped(self.service.user_color != 1)
            self.canvas.sync_board(board, last_move)
            self._update_check_marker()
        elif isinstance(self.canvas, GomokuCanvas) and isinstance(board, GomokuBoard):
            self.canvas.sync_board(board, last_move)

    def _update_check_marker(self) -> None:
        """行棋方被将军时给其将/帅套红环；终局交给终局高亮处理。"""
        board = self.service.board
        if not isinstance(board, XiangqiBoard) or not isinstance(self.canvas, XiangqiCanvas):
            return
        if self.service.game_over or not board.is_in_check():
            self.canvas.clear_check()
            return
        king = rules.find_king(board.grid, board.side_to_move)
        if king is None:
            self.canvas.clear_check()
        else:
            self.canvas.show_check(king)

    # ---- 棋种切换 ----

    def _on_game_change(self, game_type: str) -> None:
        """切换棋种：重建 GameService 与画布并重开一局（设置随迁）。"""
        if game_type == self.service.spec.game_type:
            return
        if self.ai_thinking:
            self.controls.set_game(self.service.spec.game_type)
            self.status_bar.set_status("AI 思考中，请稍后再切换棋种")
            return
        if self._factory is None or game_type not in self._factory.available_games():
            self.controls.set_game(self.service.spec.game_type)
            self.panel.show_info("该棋种当前不可用（未安装引擎）。")
            return
        self._switch_game(game_type)

    def _switch_game(self, game_type: str) -> None:
        assert self._factory is not None
        old = self.service
        new_service = self._factory.create(game_type, user_color=old.user_color)
        # 设置随迁：难度/模型/建议开关在新棋种保持不变
        new_service.config.difficulty_depth = old.config.difficulty_depth
        new_service.config.difficulty_name = old.config.difficulty_name
        new_service.config.model_name = old.config.model_name
        new_service.config.suggestion_enabled = old.config.suggestion_enabled

        self._user_result = None
        self._comment_seq += 1  # 作废旧棋种在途的解说事件
        self._suggest_seq += 1  # 作废旧局面的建议
        self._xq_selection = None

        self.service = new_service
        self.service.new_game()
        self.root.title(self._game_title())
        self.controls.apply_game(game_type)
        self.controls.set_user_color(self.service.user_color)

        self.canvas.destroy()
        self.canvas = self._build_canvas()
        self._pack_canvas()
        self.canvas.bind("<Button-3>", self._on_cancel_preview)
        # 新画布构造时只画棋盘底；必须按新对局重绘棋子（此前切换后象棋为空盘）
        self._sync_canvas()

        if self.panel.streaming:
            self.panel.end_stream()
        self.panel.clear()
        self._announce_start()
        self._maybe_ai_open()
        self._refresh_undo_button()

    # ---- 状态栏 ----

    def _update_turn_status(self) -> None:
        if self.service.game_over:
            return
        move_no = self.service.board.moves_count + 1
        color = self.service.spec.color_display(self.service.user_color)
        verb = "行棋" if self._is_xiangqi() else "落子"
        parts = [f"第 {move_no} 手，轮到你{verb}，你执{color}棋"]
        if self._is_xiangqi() and self.xiangqi_board.is_in_check():
            parts.insert(0, "将军！")
        last_text = self._last_move_text()
        if last_text:
            parts.append(last_text)
        self.status_bar.set_status(" · ".join(parts))
        self.status_bar.start_wait("你", verb)
        self._refresh_undo_button()

    def _last_move_text(self) -> str:
        """状态栏用的「上一手」文案（象棋中文记法 / 五子棋坐标）。"""
        board = self.service.board
        last = getattr(board, "last_move", lambda: None)()
        if not last:
            return ""
        move, color = last
        if isinstance(board, XiangqiBoard):
            notations = board.history_notations()
            if not notations:
                return ""
            side = "红" if color == 1 else "黑"
            return f"上一手 {side} {notations[-1]}"
        side = "黑" if color == 1 else "白"
        return f"上一手 {side} {format_coord(move)}"

    def _refresh_undo_button(self) -> None:
        self.controls.set_undo_enabled(not self.ai_thinking and self.service.can_undo)

    def _announce_start(self) -> None:
        first = self.service.spec.color_display(1)
        side = f"你执{first}先行" if self.service.user_color == 1 else f"AI 执{first}先行"
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
        if self._is_xiangqi():
            self._on_xiangqi_click(move)
        else:
            self._on_gomoku_click(move)

    def _on_gomoku_click(self, move: Move) -> None:
        """两次点击落子：第一次点空位放虚拟棋子，第二次点它才真正落子。

        第一次点击后仍可点击其它空位移动虚拟棋子；点击已占用点不会改变预选。
        """
        if self.ai_thinking or self.service.game_over or not self.service.user_turn:
            return
        if self.board.grid[move.row][move.col] != EMPTY:
            self.status_bar.set_status("此处已有棋子，请选择空位")
            return

        pending = self.go_canvas.pending_move
        if pending == move:  # 第二次点击同一虚拟棋子 → 确认落子
            self._confirm_user_move(move)
            return

        # 第一次点击（或改选其它空位）：只画虚拟棋子，不真正落子
        self.go_canvas.show_pending(move, self.service.user_color)
        if pending is None:
            self.status_bar.set_status(
                f"已预选 {format_coord(move)}：再点一次虚拟棋子确认落子，点其它空位可更换"
            )
        else:
            self.status_bar.set_status(f"已改选 {format_coord(move)}：再点一次虚拟棋子确认落子")

    def _confirm_user_move(self, move: Move) -> None:
        """确认预选落点并进入正常的用户落子 → AI 回合流程。"""
        self.go_canvas.clear_pending()
        try:
            result = self.service.user_move(move.row, move.col)
        except (IllegalMoveError, RuntimeError) as exc:
            logger.debug("用户非法落子: %s", exc)
            self.status_bar.set_status("此处不能落子，请选择空位")
            return

        self._suggest_seq += 1  # 用户已落子，丢弃在途建议
        self._sync_canvas(last_move=result.move)
        if result.game_over:
            self._handle_game_over(result)
            return

        self._start_ai_turn(user_result=result)

    def _on_xiangqi_click(self, move: Move) -> None:
        """选子走子：点己方棋子选中，点落点先放虚拟棋子，再点一次才落子。"""
        if self.ai_thinking or self.service.game_over or not self.service.user_turn:
            return
        board = self.xiangqi_board
        piece = board.grid[move.row][move.col]
        selection = self._xq_selection
        if selection is not None:
            targets = rules.legal_targets(board.grid, selection.row, selection.col)
            if (move.row, move.col) in targets:
                pending = self.xq_canvas.pending_move
                if pending is not None and (pending.to_row, pending.to_col) == (
                    move.row,
                    move.col,
                ):
                    self._play_xiangqi_move(pending)  # 第二次点击同一虚拟棋子 → 确认
                elif self._xq_virtual_piece:
                    self._preview_xiangqi_move(move)  # 先预览，等二次点击确认
                else:
                    self._play_xiangqi_move(
                        Move(selection.row, selection.col, move.row, move.col)
                    )  # 未开启虚拟棋子：点落点直接走子
                return
            if piece and rules.side_of(piece) == board.side_to_move:
                self._select_piece(move)  # 改选其它己方棋子
                return
            self.status_bar.set_status("此处不是合法落点；可点其它己方棋子改选，右键/Esc 取消")
            return
        if piece and rules.side_of(piece) == board.side_to_move:
            self._select_piece(move)
        else:
            self.status_bar.set_status("请先点击己方棋子选中")

    def _select_piece(self, move: Move) -> None:
        board = self.xiangqi_board
        self._xq_selection = move
        self.xq_canvas.clear_hint()  # 选子期间不显示建议，避免两套标记混叠
        targets = rules.legal_targets(board.grid, move.row, move.col)
        self.xq_canvas.show_selection(move, targets)
        name = PIECE_CN.get(board.grid[move.row][move.col], "?")
        if targets:
            if self._xq_virtual_piece:
                text = f"已选中{name}：点击标记预选落点，再点虚拟棋子确认；右键/Esc 取消"
            else:
                text = f"已选中{name}：点击标记落子，右键/Esc 取消"
            self.status_bar.set_status(text)
        else:
            self.status_bar.set_status(f"{name}当前没有合法落点，可改选其它棋子")

    def _preview_xiangqi_move(self, target: Move) -> None:
        """在目标点放虚拟棋子；不改变棋局，等用户再次点击确认。"""
        selection = self._xq_selection
        if selection is None:
            return
        move = Move(selection.row, selection.col, target.row, target.col)
        self.xq_canvas.show_pending(move)
        name = PIECE_CN.get(self.xiangqi_board.grid[selection.row][selection.col], "?")
        if self.xiangqi_board.grid[target.row][target.col]:
            self.status_bar.set_status(f"已预选{name}吃子：再点一次虚拟棋子确认，点其它红环可更换")
        else:
            self.status_bar.set_status(f"已预选{name}落点：再点一次虚拟棋子确认，点其它绿点可更换")

    def _play_xiangqi_move(self, move: Move) -> None:
        self._xq_selection = None
        self.xq_canvas.clear_selection()
        self._suggest_seq += 1  # 用户已走子，丢弃在途建议
        try:
            result = self.service.play_user_move(move)
        except (IllegalMoveError, RuntimeError) as exc:
            logger.debug("用户非法走子: %s", exc)
            self.status_bar.set_status("该着法不可行，请重新选择")
            return
        self._sync_canvas(last_move=result.move)
        if result.game_over:
            self._handle_game_over(result)
            return
        self._start_ai_turn(user_result=result)

    def _on_cancel_preview(self, _event: Any = None) -> None:
        """Esc / 右键取消预选或选子；随后补算一次建议，恢复棋盘提示。"""
        if self._is_xiangqi():
            if self._xq_selection is None:
                return
            if self.xq_canvas.pending_move is not None:
                # 第一次取消虚拟棋子，保留选子；再按一次才取消选子
                self.xq_canvas.clear_pending()
                self.status_bar.set_status("已取消落子：点标记重新预选，右键/Esc 取消选子")
                return
            self._xq_selection = None
            self.xq_canvas.clear_selection()
            self._update_turn_status()
            self._request_suggestion()
            return
        if self.go_canvas.pending_move is None:
            return
        self.go_canvas.clear_pending()
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
        """开关本地落子建议；关闭时清掉棋盘上的建议标记。"""
        self.service.config.suggestion_enabled = enabled
        if not enabled:
            self._suggest_seq += 1  # 作废在途建议，避免关闭后又画出来
            self.canvas.clear_hint()
            self.panel.show_info("已关闭落子建议。")
            return
        self.panel.show_info("已开启落子建议。")
        self._request_suggestion()  # 当前若轮到用户，立即补一条

    def _on_color_change(self, user_color: int) -> None:
        """切换先手方；换边影响先手，直接重开一局。"""
        if self.ai_thinking:
            self.controls.set_user_color(self.service.user_color)
            self.status_bar.set_status("AI 思考中，请稍后再切换执子方")
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
        self._xq_selection = None
        self.service.new_game()
        self._sync_canvas()
        self.panel.clear()
        self._announce_start()
        self._maybe_ai_open()
        self._refresh_undo_button()

    # ---- 悔棋 ----

    def _on_undo_shortcut(self, _event: Any = None) -> None:
        self._undo()

    def _undo(self) -> None:
        """悔棋：撤销到重新轮到自己（正常一回合两步，终局后撤销致胜一步）。"""
        if self.ai_thinking:
            self.status_bar.set_status("AI 思考中，请稍后再悔棋")
            return
        try:
            undone = self.service.undo_round()
        except RuntimeError:
            self.status_bar.set_status("当前没有可悔的棋")
            return
        self._user_result = None
        self._comment_seq += 1  # 作废旧局面的在途解说
        if self.panel.streaming:
            self.panel.end_stream()
        self._suggest_seq += 1
        self._xq_selection = None
        last = getattr(self.service.board, "last_move", lambda: None)()
        self._sync_canvas(last_move=last[0] if last else None)
        self.panel.show_info(f"已悔棋 {undone} 步。")
        self._update_turn_status()
        self._request_suggestion()

    def _maybe_ai_open(self) -> None:
        """AI 先手时，开局由 AI 先落子。"""
        if self.service.game_over or self.service.user_turn:
            return
        self._start_ai_turn(user_result=None)

    # ---- AI 回合（后台线程 + 队列回主线程） ----

    def _start_ai_turn(self, user_result: TurnResult | None) -> None:
        self.ai_thinking = True
        self._user_result = user_result
        depth = self.service.config.difficulty_depth
        if self._is_xiangqi():
            ms = DEPTH_TO_MOVETIME_MS.get(depth, DEFAULT_MOVETIME_MS)
            prefix = "AI 被将军，" if self.xiangqi_board.is_in_check() else "AI "
            self.status_bar.set_status(f"{prefix}思考中（约 {ms / 1000:g} 秒）")
            self.status_bar.start_wait("AI", "行棋")
        else:
            self.status_bar.set_status(f"AI 思考中，搜索深度 {depth}")
            self.status_bar.start_wait("AI", "落子")
        self._refresh_undo_button()

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
        self._sync_canvas(last_move=result.move)
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
        # 引擎评估（象棋）：必杀单独强调，普通评分给一行短文案
        if result.engine_eval is not None:
            if result.engine_eval.mate_in is not None:
                self.panel.show_info(f"引擎判断：{score_display(result.engine_eval)}")
            else:
                self.panel.show_info(f"引擎评估：{score_brief(result.engine_eval)}")
        self._start_commentary(result)
        # 建议单独在后台算：AI 棋子先显示，建议算完再补上
        self._request_suggestion()

    def _request_suggestion(self) -> None:
        """按当前难度深度后台计算建议（不阻塞界面，也不依赖 LLM）。"""
        if not self.service.config.suggestion_enabled:
            return
        if self.service.game_over or self.ai_thinking or not self.service.user_turn:
            return
        if self._is_xiangqi():
            if self._xq_selection is not None:
                return  # 选子期间的落点标记与建议标记会互相干扰
        elif self.canvas.pending_move is not None:
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

        user_move, ai_move = user_result.move, ai_result.move
        user_color = self.service.user_color
        board_snapshot = self.service.board.clone()
        move_db_id = ai_result.move_db_id

        # 提示词在主线程按棋种组装；失败按解说不可用处理，不开流式段
        try:
            if isinstance(board_snapshot, XiangqiBoard):
                prompt = build_xiangqi_prompt(
                    board_snapshot, user_move, ai_move, user_color, ai_result.engine_eval
                )
            elif isinstance(board_snapshot, GomokuBoard):
                prompt = build_gomoku_prompt(board_snapshot, user_move, ai_move, user_color)
            else:
                raise TypeError(f"不支持的棋盘类型: {type(board_snapshot).__name__}")
        except Exception as exc:  # noqa: BLE001
            self.panel.show_info(f"解说不可用：{exc}")
            return

        self.panel.begin_stream()  # 段落头已在 _on_ai_move 写出
        self.status_bar.set_status("解说生成中，可继续落子")

        def _on_chunk(text: str) -> None:
            self._queue.put({"type": "chunk", "text": text, "seq": seq})

        def _on_done(full: str) -> None:
            self._queue.put({"type": "commentary_end", "seq": seq, "text": full})

        def _work() -> None:
            self.commentary.generate(
                client,
                prompt,
                move_id=move_db_id,
                on_chunk=_on_chunk,
                on_done=_on_done,
            )

        run_in_background(_work)

    def _on_commentary_end(self) -> None:
        if not self.service.game_over and not self.ai_thinking:
            self._update_turn_status()

    def _show_local_suggestion(self, move: Move | None) -> None:
        """把本地引擎生成的建议画上棋盘（棋种各自的展示方式）。"""
        if not self.service.config.suggestion_enabled:
            return
        if move is None or self.service.game_over or self.ai_thinking:
            return
        if not self.service.user_turn:
            return
        if self._is_xiangqi():
            self._show_xiangqi_suggestion(move)
            return
        if self.canvas.pending_move is not None:
            return  # 用户预选期间不覆盖其虚拟棋子
        if self.board.grid[move.row][move.col] != EMPTY:
            return
        self.canvas.show_hint(move, self.service.user_color)
        self.panel.show_info(
            f"本地建议：{format_coord(move)}（点一次预选，再点一次虚拟棋子确认落子）"
        )

    def _show_xiangqi_suggestion(self, move: Move) -> None:
        """象棋建议：棋盘标出起点与终点，面板给出中文记法。"""
        board = self.xiangqi_board
        if self._xq_selection is not None:
            return  # 选子期间不画建议，避免与落点标记混叠
        if not board.is_playable(move):
            return
        self.xq_canvas.show_hint(move, self.service.user_color)
        text = notation.move_text(board.grid, move)
        self.panel.show_info(f"本地建议：{text}（绿色标记为起点与终点）")

    def _handle_game_over(self, result: TurnResult) -> None:
        self.ai_thinking = False
        self.status_bar.stop_wait()
        if result.win_line:
            self.canvas.highlight_win(result.win_line)
        elif self._is_xiangqi() and result.winner is not None:
            # 将死/困毙：高亮输方的将/帅
            king = rules.find_king(self.xiangqi_board.grid, -result.winner)
            if king is not None:
                self.xq_canvas.highlight_win([Move(king[0], king[1])])
        if result.winner is None:
            status = "对局结束：平局，棋盘已满"
        elif result.winner == self.service.user_color:
            status = "对局结束：你赢了"
        else:
            status = "对局结束：AI 获胜"
        if self._is_xiangqi() and result.winner is not None:
            reason = "将死" if self.xiangqi_board.end_reason == "checkmate" else "困毙"
            status = f"{status}（{reason}）"
        self.status_bar.set_status(status)
        self.panel.show_info(f"{status}，点击「重新开局」再来一局。")
        self._refresh_undo_button()
        logger.info("对局结束展示: winner=%s", result.winner)
