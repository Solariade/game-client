"""AnalysisPanel 有序输出单测（纯 Tk 控件，无 LLM / 无后台线程）。"""

from __future__ import annotations

import tkinter as tk

import pytest

from app.ui.analysis_panel import AnalysisPanel


@pytest.fixture()
def panel(tk_root: tk.Tk):
    yield AnalysisPanel(tk_root)


def text_of(panel: AnalysisPanel) -> str:
    return panel.text.get("1.0", "end")


def test_first_header_no_leading_blank(panel: AnalysisPanel) -> None:
    panel.begin_turn("第 1 回合")
    panel.append_chunk("黑落天元。")
    panel.end_stream()
    assert text_of(panel).startswith("第 1 回合\n")
    assert not text_of(panel).startswith("\n")


def test_second_header_has_blank_gap(panel: AnalysisPanel) -> None:
    panel.begin_turn("第 1 回合")
    panel.append_chunk("黑落天元。")
    panel.end_stream()
    panel.begin_turn("第 2 回合")
    panel.append_chunk("白靠右侧。")
    panel.end_stream()
    text = text_of(panel)
    assert "\n\n第 2 回合" in text
    assert text.index("第 1 回合") < text.index("第 2 回合")


def test_info_during_stream_pends_until_end(panel: AnalysisPanel) -> None:
    panel.begin_turn("第 1 回合")
    panel.append_chunk("黑落天元。")
    panel.show_info("对局结束：你赢了")
    mid = text_of(panel)
    assert "对局结束" not in mid  # 流式进行中不插入
    panel.append_chunk("白防守。")
    panel.end_stream()
    text = text_of(panel)
    assert "白防守。" in text
    assert "对局结束" in text
    assert text.index("白防守。") < text.index("对局结束")  # 按到达顺序输出


def test_begin_during_stream_pends(panel: AnalysisPanel) -> None:
    panel.begin_turn("第 1 回合")
    panel.append_chunk("黑落天元。")
    panel.begin_turn("第 2 回合")  # 上一段未 end_stream 就开新段：先挂起
    assert "第 2 回合" not in text_of(panel)
    panel.end_stream()
    text = text_of(panel)
    assert "\n\n第 2 回合" in text
    assert text.index("第 1 回合") < text.index("第 2 回合")


def test_show_header_without_stream(panel: AnalysisPanel) -> None:
    """没有解说模型时也要输出回合标题，且不进入流式状态。"""
    panel.show_header("第 1 回合")
    assert text_of(panel).startswith("第 1 回合\n")
    assert panel.streaming is False
    panel.show_info("本地建议：H8（点击虚线棋子即落子）")
    assert "本地建议：H8" in text_of(panel)


def test_begin_stream_after_header(panel: AnalysisPanel) -> None:
    """标题先由 show_header 写出，随后 begin_stream 接收解说文本。"""
    panel.show_header("第 1 回合")
    panel.begin_stream()
    panel.append_chunk("黑落天元。")
    panel.end_stream()
    text = text_of(panel)
    assert "第 1 回合\n黑落天元。" in text


def test_chunk_without_stream_dropped(panel: AnalysisPanel) -> None:
    panel.append_chunk("孤儿分块")
    assert text_of(panel) == "\n"


def test_clear_resets_state(panel: AnalysisPanel) -> None:
    panel.begin_turn("第 1 回合")
    panel.append_chunk("黑落天元。")
    panel.show_info("挂起信息")
    panel.clear()
    assert text_of(panel) == "\n"
    assert panel.streaming is False
    panel.append_chunk("清空后的迟到分块")
    assert text_of(panel) == "\n"  # 无在途流，迟到内容被丢弃
