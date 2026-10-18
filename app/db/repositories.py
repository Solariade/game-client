"""games / moves 仓储：封装增查。"""

from __future__ import annotations

import sqlite3
from typing import Any

GAME_TYPE_GOMOKU = "gomoku"


class GameRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def create_game(
        self,
        game_type: str = GAME_TYPE_GOMOKU,
        model_name: str | None = None,
        difficulty: str | None = None,
        user_color: str = "black",
    ) -> int:
        """新建对局记录，返回 game_id。"""
        cur = self._conn.execute(
            "INSERT INTO games (game_type, model_name, difficulty, user_color) VALUES (?, ?, ?, ?)",
            (game_type, model_name, difficulty, user_color),
        )
        self._conn.commit()
        return int(cur.lastrowid or 0)

    def finish_game(self, game_id: int, result: str) -> None:
        """更新对局结果：'user_win' / 'ai_win' / 'draw'。"""
        self._conn.execute("UPDATE games SET result = ? WHERE id = ?", (result, game_id))
        self._conn.commit()

    def get_game(self, game_id: int) -> dict[str, Any] | None:
        cur = self._conn.execute("SELECT * FROM games WHERE id = ?", (game_id,))
        row = cur.fetchone()
        return dict(row) if row else None


class MoveRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add_move(
        self,
        game_id: int,
        move_number: int,
        player: str,
        row: int,
        col: int,
        llm_commentary: str | None = None,
    ) -> int:
        """写入一步棋，返回 move id。"""
        cur = self._conn.execute(
            "INSERT INTO moves (game_id, move_number, player, position, llm_commentary) "
            "VALUES (?, ?, ?, ?, ?)",
            (game_id, move_number, player, f"{row},{col}", llm_commentary),
        )
        self._conn.commit()
        return int(cur.lastrowid or 0)

    def update_commentary(self, move_id: int, commentary: str) -> None:
        """流式解说完成后回填该步的解说全文。"""
        self._conn.execute(
            "UPDATE moves SET llm_commentary = ? WHERE id = ?", (commentary, move_id)
        )
        self._conn.commit()

    def list_moves(self, game_id: int) -> list[dict[str, Any]]:
        cur = self._conn.execute(
            "SELECT * FROM moves WHERE game_id = ? ORDER BY move_number", (game_id,)
        )
        return [dict(row) for row in cur.fetchall()]
