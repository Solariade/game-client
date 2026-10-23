"""ControlsPanel 设置区单测：模型下拉的空选项与默认选择。"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

import pytest

from app.ai.difficulty import DEFAULT_DIFFICULTY
from app.ui.controls import ControlsPanel

# 与 MainWindow 一致：首项内容空着（空串）+ 已配置模型
MODELS = [("", ""), ("glm", "GLM")]


@pytest.fixture()
def panel(tk_root: tk.Tk) -> ControlsPanel:
    yield ControlsPanel(
        tk_root,
        model_names=MODELS,
        on_model_change=lambda _n: None,
        on_difficulty_change=lambda _d: None,
        on_color_change=lambda _c: None,
        on_suggestion_change=lambda _s: None,
        on_restart=lambda: None,
    )


def test_blank_is_default_model(panel: ControlsPanel) -> None:
    """模型下拉默认内容为空：不进行 AI 解说。"""
    assert panel.current_model == ""
    assert panel._model_var.get() == ""


def test_select_model_by_display(panel: ControlsPanel) -> None:
    panel._model_var.set("GLM")
    assert panel.current_model == "glm"


def test_difficulty_default(panel: ControlsPanel) -> None:
    assert panel.current_difficulty is DEFAULT_DIFFICULTY


def test_user_color_default_and_set(panel: ControlsPanel) -> None:
    assert panel.current_user_color == 1  # 默认我执黑
    panel.set_user_color(-1)
    assert panel.current_user_color == -1
    panel.set_user_color(1)
    assert panel.current_user_color == 1


def test_suggestion_default_enabled(panel: ControlsPanel) -> None:
    """落棋建议默认开启。"""
    assert panel.suggestion_enabled is True
    panel._suggestion_var.set("关")
    assert panel.suggestion_enabled is False


def test_layout_is_three_by_two(panel: ControlsPanel) -> None:
    """设置区为 3×2 宫格：第一行 3 格，第二行 2 格。"""
    # 5 个设置格 + 底部重新开局按钮
    cells = [
        w
        for w in panel.winfo_children()
        if isinstance(w, ttk.Frame) and w.grid_info().get("row") in (0, 1)
    ]
    assert len(cells) == 5
    assert sum(1 for w in cells if w.grid_info()["row"] == 0) == 3
    assert sum(1 for w in cells if w.grid_info()["row"] == 1) == 2


def make_multi_game_panel(tk_root: tk.Tk, selected: list[str]) -> ControlsPanel:
    """带棋种切换的设置区（记录回调触发）。"""
    panel = ControlsPanel(
        tk_root,
        model_names=MODELS,
        on_model_change=lambda _n: None,
        on_difficulty_change=lambda _d: None,
        on_color_change=lambda _c: None,
        on_suggestion_change=lambda _s: None,
        on_restart=lambda: None,
        game_options=[("gomoku", "五子棋"), ("xiangqi", "象棋")],
        on_game_change=selected.append,
    )
    return panel


class TestGameDropdown:
    def test_default_single_game_disabled(self, panel: ControlsPanel) -> None:
        """未传 game_options：棋种下拉只有五子棋且禁用。"""
        assert panel.current_game == "gomoku"
        assert str(panel._game_var.get()) == "五子棋"

    def test_multi_game_current_game_mapping(self, tk_root: tk.Tk) -> None:
        panel = make_multi_game_panel(tk_root, [])
        assert panel.current_game == "gomoku"
        panel._game_var.set("象棋")
        assert panel.current_game == "xiangqi"

    def test_game_change_callback_fires(self, tk_root: tk.Tk) -> None:
        """下拉选中象棋 → 触发 <<ComboboxSelected>> → 回调收到内部名。"""
        selected: list[str] = []
        panel = make_multi_game_panel(tk_root, selected)
        panel._game_var.set("象棋")
        panel._game_box.event_generate("<<ComboboxSelected>>")
        tk_root.update()
        assert selected == ["xiangqi"]

    def test_set_game_reverts(self, tk_root: tk.Tk) -> None:
        panel = make_multi_game_panel(tk_root, [])
        panel._game_var.set("象棋")
        panel.set_game("gomoku")
        assert panel.current_game == "gomoku"


class TestUndoButton:
    def test_no_undo_button_without_callback(self, panel: ControlsPanel) -> None:
        assert panel._undo_button is None
        panel.set_undo_enabled(True)  # 无按钮时应静默忽略

    def test_undo_button_toggles_and_invokes(self, tk_root: tk.Tk) -> None:
        calls: list[int] = []
        panel = ControlsPanel(
            tk_root,
            model_names=MODELS,
            on_model_change=lambda _n: None,
            on_difficulty_change=lambda _d: None,
            on_color_change=lambda _c: None,
            on_suggestion_change=lambda _s: None,
            on_restart=lambda: None,
            on_undo=lambda: calls.append(1),
        )
        assert panel._undo_button is not None
        panel.set_undo_enabled(False)
        assert str(panel._undo_button["state"]) == "disabled"
        panel.set_undo_enabled(True)
        panel._undo_button.invoke()
        assert calls == [1]


class TestColorCellPerGame:
    def test_default_is_gomoku_black(self, tk_root: tk.Tk) -> None:
        panel = make_multi_game_panel(tk_root, [])
        assert panel.current_user_color == 1
        panel.set_user_color(-1)
        assert panel.current_user_color == -1

    def test_apply_game_keeps_first_player_choice(self, tk_root: tk.Tk) -> None:
        """切到象棋后标签变执红、取值变我执红/AI执红，先手选择保持。"""
        panel = make_multi_game_panel(tk_root, [])
        panel.set_user_color(-1)  # AI 先手
        panel.apply_game("xiangqi")
        assert panel._color_var.get() == "AI执红"
        assert panel.current_user_color == -1
        panel.apply_game("gomoku")
        assert panel._color_var.get() == "AI执黑"
        assert panel.current_user_color == -1

    def test_apply_game_first_player(self, tk_root: tk.Tk) -> None:
        panel = make_multi_game_panel(tk_root, [])
        panel.apply_game("xiangqi")
        assert panel._color_var.get() == "我执红"
        assert panel.current_user_color == 1
