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
