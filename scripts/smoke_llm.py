"""真实 LLM 流式解说冒烟测试（开发用脚本）。

使用 .env 中的默认模型，会真实调用 API 并产生费用。

用法：
    uv run python scripts/smoke_llm.py
"""

from app.core.base_game import Move
from app.core.gomoku.board import GomokuBoard
from app.llm.openai_compat import OpenAICompatClient
from app.llm.prompts import build_gomoku_prompt
from app.settings import load_settings


def main() -> None:
    settings = load_settings()
    cfg = settings.provider_config(settings.DEFAULT_LLM)
    print(f"模型: {settings.DEFAULT_LLM} / {cfg['model']} @ {cfg['base_url']}")

    client = OpenAICompatClient(
        name=settings.DEFAULT_LLM,
        display_name=settings.DEFAULT_LLM,
        api_key=cfg["api_key"],
        base_url=cfg["base_url"],
        model=cfg["model"],
    )

    board = GomokuBoard()
    for mv, color in [((7, 7), 1), ((7, 8), -1), ((8, 8), 1)]:
        board.place(Move(*mv), color)
    prompt = build_gomoku_prompt(board, user_move=Move(8, 8), ai_move=Move(7, 8), user_color=1)

    parts = []
    for chunk in client.stream_commentary(prompt):
        parts.append(chunk)
        print(chunk, end="", flush=True)
    print("\n--- 完成，共", len("".join(parts)), "字 ---")


if __name__ == "__main__":
    main()
