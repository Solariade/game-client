"""输出顺序冒烟（开发用脚本）：慢速假 LLM 验证解说面板有序输出与建议落子。

流程：默认「空白」模型下落子一轮，确认不产生任何解说；随后选择模型重开，
用户落子后 AI 回应并开始第一段慢速解说；在第一段流出中途用户再落子，
新一段解说开始时旧流被作废。断言：
- 空白默认：无回合段落、无解说状态、无建议落子；
- “第 2 回合”与“第 1 回合”之间有空行间隔；
- 第 1 回合只保留被作废前已到达的分块，无后续残留；
- 第 2 回合分块完整且不混入第 1 回合内容；
- 第 2 段末尾的建议落子被解析为棋盘上的虚拟棋子，点击后确认落子。

用法：
    uv run python scripts/smoke_order.py
"""

import sys
import time
import tkinter as tk
from collections.abc import Iterator

from app.bootstrap import bootstrap
from app.core.base_game import Move
from app.ui.main_window import MainWindow

# 第 1 段解说各分块前的延迟（秒）：首块快速到达，后两块落在作废之后
DELAYS_FIRST = (1.0, 5.0, 5.0)
DELAYS_NEXT = (0.3, 0.3, 0.3)
# 第 2 段末尾给出建议落子（H9 = 行 8 列 7），验证虚拟棋子
SUGGEST_TAIL = "建议落子：H9"


class SlowFakeClient:
    """慢速假 LLM：按调用次数区分标记，接口与 OpenAICompatClient 对齐。"""

    def __init__(self) -> None:
        self.calls = 0

    def stream_commentary(self, prompt: str) -> Iterator[str]:
        self.calls += 1
        tag = "流一" if self.calls == 1 else "流二"
        delays = DELAYS_FIRST if self.calls == 1 else DELAYS_NEXT
        for delay, suffix in zip(delays, "甲乙丙", strict=True):
            time.sleep(delay)
            yield f"{tag}{suffix}"
        if self.calls == 2:
            yield SUGGEST_TAIL


def main() -> None:
    ctx = bootstrap()
    fake = SlowFakeClient()
    for name in list(ctx.llm_registry._clients):
        ctx.llm_registry._clients[name] = fake  # type: ignore[assignment]

    root = tk.Tk()
    root.withdraw()  # 隐藏窗口，避免人工点击干扰自动化断言
    win = MainWindow(root, ctx.game_service, ctx.commentary_service, ctx.llm_registry)
    results: list[tuple[bool, str]] = []

    def report(name: str, cond: bool, detail: str = "") -> None:
        results.append((cond, name))
        print(f"  [{'PASS' if cond else 'FAIL'}] {name} {detail}")

    def blank_click() -> None:
        print("默认空白状态下模拟点击 (7,7)，AI 回应但不应产生解说")
        win._on_board_click(Move(7, 7))

    def check_blank_then_enable() -> None:
        text = win.panel.text.get("1.0", "end")
        report("空白默认无解说回合", "回合" not in text)
        report("空白默认无解说状态", "解说" not in win.status_bar.text, win.status_bar.text)
        report("空白默认回到用户回合", "轮到你落子" in win.status_bar.text)
        report("空白默认无建议落子", win.canvas.hint_move is None, f"hint={win.canvas.hint_move}")
        print("选择解说模型并重开，进入有序输出验证")
        win._on_model_change(ctx.llm_registry.default_name)
        win._restart()

    def click_first() -> None:
        print("模拟点击 (7,7)，触发第 1 段解说")
        win._on_board_click(Move(7, 7))

    def click_second() -> None:
        print("解说流出中途模拟点击 (8,8)，触发第 2 段解说")
        win._on_board_click(Move(8, 8))

    def final_check() -> None:
        report(
            "点击虚拟棋子已落子",
            ctx.game_service.board.grid[8][7] == ctx.game_service.user_color,
        )
        report("落子后虚拟棋子已清除", win.canvas.hint_move is None, f"hint={win.canvas.hint_move}")
        ok = all(cond for cond, _ in results)
        print("结果:", "ALL PASS" if ok else "FAILED")
        root.quit()
        root.destroy()
        sys.exit(0 if ok else 1)

    def check_order_and_hint() -> None:
        text = win.panel.text.get("1.0", "end")
        print("面板当前内容：")
        print(text)
        ok_header1 = "第 1 回合" in text
        ok_header2 = "第 2 回合" in text
        report("出现第 1 回合段落头", ok_header1)
        report("出现第 2 回合段落头", ok_header2)
        if ok_header1 and ok_header2:
            i1, i2 = text.index("第 1 回合"), text.index("第 2 回合")
            report("回合顺序正确", i1 < i2)
            head, tail = text[:i2], text[i2:]
            report("回合头之间空一行", "\n\n第 2 回合" in text)
            report("第 1 段首块已输出", "流一甲" in head)
            report("第 1 段作废后无残留", "流一乙" not in text and "流一丙" not in text)
            report("第 2 段分块完整", all(p in tail for p in ("流二甲", "流二乙", "流二丙")))

        report(
            "建议落子显示为虚拟棋子",
            win.canvas.hint_move == Move(8, 7),
            f"hint={win.canvas.hint_move}",
        )
        print("模拟点击虚拟棋子位置 (8,7)，确认落子")
        win._on_board_click(Move(8, 7))
        root.after(3000, final_check)

    root.after(600, blank_click)
    root.after(3000, check_blank_then_enable)
    root.after(3800, click_first)
    root.after(7300, click_second)  # 介于流一甲与流一乙之间，验证作废
    root.after(12800, check_order_and_hint)  # 第 2 段已流出完毕，建议落子已解析
    root.mainloop()


if __name__ == "__main__":
    main()
