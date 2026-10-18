"""端到端交互冒烟（开发用脚本）：模拟点击、AI 回应、流式解说、落库全链路。

阶段 1：用户执黑，点击落子后 AI 回应并流式解说回填；
阶段 2：切换为 AI 执黑，验证自动重开且 AI 先行落子。
不依赖人工点击：直接在主线程调用 MainWindow 回调，再进入 mainloop
让 queue 轮询与后台线程完成 AI 搜索与 LLM 解说。

用法：
    uv run python scripts/smoke_e2e.py
"""

import sys
import tkinter as tk

from app.bootstrap import bootstrap
from app.core.base_game import Move
from app.ui.main_window import MainWindow


def main() -> None:
    ctx = bootstrap()
    root = tk.Tk()
    root.withdraw()  # 隐藏窗口，避免人工点击干扰自动化断言
    win = MainWindow(root, ctx.game_service, ctx.commentary_service, ctx.llm_registry)
    win._on_model_change(ctx.llm_registry.default_name)  # 默认空白不解说，冒烟先选模型
    service = ctx.game_service
    results: list[tuple[bool, str]] = []

    def report(name: str, cond: bool, detail: str = "") -> None:
        results.append((cond, name))
        print(f"  [{'PASS' if cond else 'FAIL'}] {name} {detail}")

    def phase1_check_and_switch() -> None:
        print("阶段 1 检查：你执黑")
        moves = service.move_repo.list_moves(service.game_id)
        commentary = [m["llm_commentary"] for m in moves if m["llm_commentary"]]
        report(
            "用户与 AI 各落一子",
            service.board.moves_count == 2,
            f"moves={service.board.moves_count}",
        )
        report("moves 表 2 行", len(moves) == 2, f"rows={len(moves)}")
        report("AI 已停止思考", win.ai_thinking is False)
        report(
            "解说已回填",
            len(commentary) >= 1,
            f"len={len(commentary[0]) if commentary else 0}",
        )
        if commentary:
            report("解说非降级文案", "解说不可用" not in commentary[0])
        report("状态栏显示回合提示", "轮到你落子" in win.status_bar.text, win.status_bar.text)
        timer = win.status_bar.timer_text
        report(
            "读秒显示等待你落子",
            timer.startswith("等待 你 落子") and timer.endswith("秒"),
            timer,
        )
        try:
            report(
                "读秒连续累计",
                int(timer.replace("等待 你 落子", "").replace("秒", "")) >= 10,
                timer,
            )
        except ValueError:
            report("读秒连续累计", False, timer)

        print("切换执黑方为 AI")
        win._on_color_change(-1)

    def phase2_check() -> None:
        print("阶段 2 检查：AI 执黑")
        report("已重开新对局", service.board.moves_count >= 1, f"moves={service.board.moves_count}")
        first = service.board.history()[0] if service.board.history() else None
        report("AI 已执黑先行", first is not None and first[1] == 1, f"首手={first}")
        report("用户为白棋", service.user_color == -1)
        report("状态栏提示用户落子", "轮到你落子" in win.status_bar.text, win.status_bar.text)
        report(
            "读秒重开归零",
            win.status_bar.timer_text.startswith("等待 你 落子"),
            win.status_bar.timer_text,
        )

        ok = all(cond for cond, _ in results)
        print("结果:", "ALL PASS" if ok else "FAILED")
        root.quit()
        root.destroy()
        sys.exit(0 if ok else 1)

    def do_click() -> None:
        print("模拟点击 (7,7)")
        win._on_board_click(Move(7, 7))

    root.after(600, do_click)
    root.after(20000, phase1_check_and_switch)
    root.after(26000, phase2_check)
    root.mainloop()


if __name__ == "__main__":
    main()
