"""MainWindow 棋种切换与象棋选子走子冒烟（Tk 不可用时自动跳过）。

覆盖 M14：切换重建 service/画布、选子 → 落点 → 走子、Esc 取消、
将死终局高亮输方将/帅与状态文案；另含布局回归（画布居左、象棋默认启动）。
"""

from __future__ import annotations

import time
import tkinter as tk
from dataclasses import replace
from typing import Any

from app.ai.base_engine import BaseEngine
from app.core.base_game import Move
from app.core.xiangqi.board import XiangqiBoard
from app.services.commentary_service import CommentaryService
from app.services.game_service import GameService
from app.services.game_spec import GameServiceFactory, make_xiangqi_spec
from app.ui.boards.gomoku_canvas import GomokuCanvas
from app.ui.boards.xiangqi_canvas import PIECE_TAG, SELECT_TAG, WIN_TAG, XiangqiCanvas
from app.ui.main_window import MainWindow

# 炮二平五（红）与黑马 8 进 7（黑）
H2E2 = (7, 7, 7, 4)

# 黑方仅剩将（0,4）；红双兵（1,3）（1,5）封住退路，红车（2,4）升一步即绝杀
MATE_FEN = "4k4/3P1P3/4R4/9/9/9/9/9/3K5/9 w - - 0 1"


class FirstMoveEngine(BaseEngine):
    """永远返回第一个合法着法的桩引擎（两棋种通用，线程安全无需脚本）。"""

    available = True

    def search(self, game: Any, depth: int, ai_color: int | None = None) -> Move:
        return game.valid_moves()[0]


class StubRegistry:
    available: list[str] = []

    def display_name(self, name: str) -> str:
        return name

    def get(self, name: str) -> Any:
        raise RuntimeError("无可用模型")


def _pump_until(tk_root: tk.Tk, predicate: Any, timeout: float = 3.0) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        tk_root.update()
        if predicate():
            return True
        time.sleep(0.02)
    return False


def make_window(tk_root: tk.Tk, *, virtual_piece: bool = True) -> MainWindow:
    factory = GameServiceFactory(
        engines={"gomoku": FirstMoveEngine(), "xiangqi": FirstMoveEngine()}
    )
    service = factory.create("gomoku", user_color=1)
    return MainWindow(
        tk_root,
        service,
        CommentaryService(),
        StubRegistry(),
        service_factory=factory,
        xiangqi_virtual_piece=virtual_piece,
    )


class TestGameSwitch:
    def test_switch_to_xiangqi_rebuilds_service_and_canvas(self, tk_root: tk.Tk) -> None:
        mw = make_window(tk_root)
        assert isinstance(mw.canvas, GomokuCanvas)

        mw._on_game_change("xiangqi")

        assert mw.service.spec.game_type == "xiangqi"
        assert isinstance(mw.canvas, XiangqiCanvas)
        assert mw.root.title() == "game-client · 象棋 AI 对弈"
        assert isinstance(mw.service.board, XiangqiBoard)
        text = mw.panel.text.get("1.0", "end")
        assert "你执红先行" in text

    def test_switch_back_to_gomoku(self, tk_root: tk.Tk) -> None:
        mw = make_window(tk_root)
        mw._on_game_change("xiangqi")
        mw._on_game_change("gomoku")
        assert mw.service.spec.game_type == "gomoku"
        assert isinstance(mw.canvas, GomokuCanvas)
        assert mw.board.size == 15

    def test_switch_to_xiangqi_redraws_initial_pieces(self, tk_root: tk.Tk) -> None:
        """切换重建画布后必须按新对局重绘：此前只画了空棋盘（打包版尤易察觉）。"""
        mw = make_window(tk_root)
        mw._on_game_change("xiangqi")
        assert len(mw.canvas.find_withtag(PIECE_TAG)) == 64

        # 来回切换后仍应保留 32 子的完整棋盘
        mw._on_game_change("gomoku")
        mw._on_game_change("xiangqi")
        assert len(mw.canvas.find_withtag(PIECE_TAG)) == 64

    def test_color_change_flips_xiangqi_board(self, tk_root: tk.Tk) -> None:
        """执黑时翻转棋盘，让黑子位于玩家一侧（下方）。"""
        mw = make_window(tk_root)
        mw._on_game_change("xiangqi")
        assert mw.canvas._flipped is False  # 默认执红，红在下

        mw._on_color_change(-1)
        assert mw.service.user_color == -1
        assert mw.canvas._flipped is True
        assert _pump_until(tk_root, lambda: not mw.ai_thinking)

        mw._on_color_change(1)
        assert mw.canvas._flipped is False

    def test_switch_preserves_settings(self, tk_root: tk.Tk) -> None:
        mw = make_window(tk_root)
        mw.service.config.difficulty_depth = 5
        mw.service.config.suggestion_enabled = False
        mw._on_game_change("xiangqi")
        assert mw.service.config.difficulty_depth == 5
        assert mw.service.config.suggestion_enabled is False


class TestLayoutAndDefaultGame:
    def test_canvas_packs_left_of_side_panel(self, tk_root: tk.Tk) -> None:
        """画布固定在右面板左侧：初始与切换重建后都成立（pack 按入列顺序分配）。"""
        mw = make_window(tk_root)
        slaves = mw._canvas_master.pack_slaves()
        assert slaves.index(mw.canvas) < slaves.index(mw._side_panel)

        mw._on_game_change("xiangqi")
        slaves = mw._canvas_master.pack_slaves()
        assert slaves.index(mw.canvas) < slaves.index(mw._side_panel)

    def test_window_starts_on_xiangqi_service(self, tk_root: tk.Tk) -> None:
        """以象棋服务直接建窗：画布/标题/棋种下拉初始即象棋。"""
        factory = GameServiceFactory(
            engines={"gomoku": FirstMoveEngine(), "xiangqi": FirstMoveEngine()}
        )
        mw = MainWindow(
            tk_root,
            factory.create("xiangqi", user_color=1),
            CommentaryService(),
            StubRegistry(),
            service_factory=factory,
        )
        assert isinstance(mw.canvas, XiangqiCanvas)
        assert mw.controls.current_game == "xiangqi"
        assert mw.root.title() == "game-client · 象棋 AI 对弈"
        assert "你执红先行" in mw.panel.text.get("1.0", "end")
        # 执子格文案必须跟随棋种：象棋是「我执红」，不能残留五子棋的「我执黑」
        assert mw.controls._color_var.get() == "我执红"


class TestXiangqiInteraction:
    def make_xiangqi_window(self, tk_root: tk.Tk) -> MainWindow:
        return make_window(tk_root)

    def test_select_then_move_full_flow(self, tk_root: tk.Tk) -> None:
        mw = self.make_xiangqi_window(tk_root)
        mw._on_game_change("xiangqi")

        mw._on_board_click(Move(7, 7))  # 选中红炮（h2）
        assert mw._xq_selection == Move(7, 7)
        assert len(mw.canvas.find_withtag(SELECT_TAG)) > 1  # 光环 + 落点
        assert "已选中" in mw.status_bar.text

        mw._on_board_click(Move(7, 4))  # 第一次点落点：只放虚拟棋子
        assert mw.service.board.moves_count == 0
        assert mw._xq_selection == Move(7, 7)
        assert mw.canvas.pending_move == Move(7, 7, 7, 4)
        assert "预选" in mw.status_bar.text

        mw._on_board_click(Move(7, 4))  # 再次点击虚拟棋子：确认炮二平五
        assert mw._xq_selection is None
        assert mw.canvas.pending_move is None

        # AI 回合在后台线程；ai_thinking 由队列事件回主线程后才清零，泵它最稳
        assert _pump_until(tk_root, lambda: not mw.ai_thinking)
        assert mw.service.board.moves_count == 2

    def test_virtual_piece_disabled_moves_immediately(self, tk_root: tk.Tk) -> None:
        """默认关闭虚拟棋子：点合法落点直接走子，不出现待确认状态。"""
        mw = make_window(tk_root, virtual_piece=False)
        mw._on_game_change("xiangqi")
        mw._on_board_click(Move(7, 7))  # 选红炮
        mw._on_board_click(Move(7, 4))  # 点落点：立即炮二平五
        assert mw.canvas.pending_move is None
        assert mw.service.board.moves_count >= 1  # 用户着法已同步落盘
        assert _pump_until(tk_root, lambda: not mw.ai_thinking)
        assert mw.service.board.moves_count == 2

    def test_preview_can_be_moved_to_another_target(self, tk_root: tk.Tk) -> None:
        """预选后点另一个合法落点只移动虚拟棋子，不落子。"""
        mw = self.make_xiangqi_window(tk_root)
        mw._on_game_change("xiangqi")
        mw._on_board_click(Move(7, 7))
        mw._on_board_click(Move(7, 4))  # 预选炮二平五
        mw._on_board_click(Move(4, 7))  # 改选另一落点（炮二进四）
        assert mw.canvas.pending_move == Move(7, 7, 4, 7)
        assert mw.service.board.moves_count == 0

    def test_escape_cancels_pending_before_selection(self, tk_root: tk.Tk) -> None:
        """Esc 先取消虚拟棋子并保留选子，再按一次才取消选子。"""
        mw = self.make_xiangqi_window(tk_root)
        mw._on_game_change("xiangqi")
        mw._on_board_click(Move(7, 7))
        mw._on_board_click(Move(7, 4))

        mw._on_cancel_preview()
        assert mw.canvas.pending_move is None
        assert mw._xq_selection == Move(7, 7)
        assert len(mw.canvas.find_withtag(SELECT_TAG)) > 0

        mw._on_cancel_preview()
        assert mw._xq_selection is None
        assert len(mw.canvas.find_withtag(SELECT_TAG)) == 0

    def test_click_enemy_piece_prompts_select_own(self, tk_root: tk.Tk) -> None:
        mw = self.make_xiangqi_window(tk_root)
        mw._on_game_change("xiangqi")
        mw._on_board_click(Move(0, 0))  # 黑车（轮红走，不可选）
        assert mw._xq_selection is None
        assert "请先点击己方棋子" in mw.status_bar.text

    def test_reselect_other_own_piece(self, tk_root: tk.Tk) -> None:
        mw = self.make_xiangqi_window(tk_root)
        mw._on_game_change("xiangqi")
        mw._on_board_click(Move(7, 7))  # 选红炮
        mw._on_board_click(Move(9, 8))  # 改选红马
        assert mw._xq_selection == Move(9, 8)

    def test_illegal_target_keeps_selection_with_hint(self, tk_root: tk.Tk) -> None:
        mw = self.make_xiangqi_window(tk_root)
        mw._on_game_change("xiangqi")
        mw._on_board_click(Move(7, 7))  # 选红炮
        mw._on_board_click(Move(5, 4))  # 非炮的合法落点（十字之外）
        assert mw._xq_selection == Move(7, 7)  # 选子保留并提示
        assert "不是合法落点" in mw.status_bar.text

    def test_escape_cancels_selection(self, tk_root: tk.Tk) -> None:
        mw = self.make_xiangqi_window(tk_root)
        mw._on_game_change("xiangqi")
        mw._on_board_click(Move(7, 7))
        mw._on_cancel_preview()
        assert mw._xq_selection is None
        assert len(mw.canvas.find_withtag(SELECT_TAG)) == 0

    def test_undo_restores_position_and_disables_button(self, tk_root: tk.Tk) -> None:
        mw = self.make_xiangqi_window(tk_root)
        mw._on_game_change("xiangqi")
        mw._on_board_click(Move(7, 7))
        mw._on_board_click(Move(7, 4))  # 预选
        mw._on_board_click(Move(7, 4))  # 确认炮二平五
        assert _pump_until(tk_root, lambda: not mw.ai_thinking)
        assert mw.service.board.moves_count == 2
        assert str(mw.controls._undo_button["state"]) == "normal"

        mw._undo()

        assert mw.service.board.moves_count == 0
        assert "已悔棋" in mw.panel.text.get("1.0", "end")
        assert str(mw.controls._undo_button["state"]) == "disabled"


class TestXiangqiEndgame:
    def test_checkmate_highlights_loser_king(self, tk_root: tk.Tk) -> None:
        """车升一步绝杀：状态报将死、你赢了，棋盘高亮黑将。"""
        spec = replace(make_xiangqi_spec(), game_factory=lambda: XiangqiBoard(MATE_FEN))
        service = GameService(engine=FirstMoveEngine(), user_color=1, spec=spec)
        mw = MainWindow(tk_root, service, CommentaryService(), StubRegistry())

        mw._on_board_click(Move(2, 4))  # 选红车
        mw._on_board_click(Move(1, 4))  # 预选升一步
        mw._on_board_click(Move(1, 4))  # 确认 = 绝杀

        assert service.game_over
        assert "你赢了" in mw.status_bar.text
        assert "将死" in mw.status_bar.text
        assert len(mw.canvas.find_withtag(WIN_TAG)) == 1  # 黑将被高亮
