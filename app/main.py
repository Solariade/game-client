"""程序入口：装配依赖、启动 UI。"""

from __future__ import annotations

import logging
import sys
import tkinter as tk
from tkinter import messagebox

from app.bootstrap import bootstrap
from app.common.errors import AppError
from app.ui.main_window import MainWindow

logger = logging.getLogger(__name__)


def main() -> int:
    try:
        ctx = bootstrap()
    except AppError as exc:
        root = tk.Tk()
        root.withdraw()
        messagebox.showerror("game-client 启动失败", str(exc))
        return 1
    except Exception:
        logging.exception("启动失败（未预期异常）")
        return 1

    root = tk.Tk()
    MainWindow(
        root,
        ctx.game_service,
        ctx.commentary_service,
        ctx.llm_registry,
        service_factory=ctx.game_factory,
        xiangqi_virtual_piece=ctx.settings.XIANGQI_VIRTUAL_PIECE,
    )
    root.mainloop()
    return 0


if __name__ == "__main__":
    sys.exit(main())
