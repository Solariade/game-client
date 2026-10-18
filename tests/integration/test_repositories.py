"""仓储层集成测试：临时 SQLite 文件。"""

from __future__ import annotations

import sqlite3

import pytest

from app.db.connection import connect
from app.db.repositories import GameRepository, MoveRepository


@pytest.fixture
def conn(tmp_path) -> sqlite3.Connection:
    return connect(tmp_path / "test.db")


class TestGameRepository:
    def test_create_and_get(self, conn) -> None:
        repo = GameRepository(conn)
        gid = repo.create_game("gomoku", model_name="glm", difficulty="中等", user_color="black")
        game = repo.get_game(gid)
        assert game is not None
        assert game["game_type"] == "gomoku"
        assert game["model_name"] == "glm"
        assert game["difficulty"] == "中等"
        assert game["user_color"] == "black"
        assert game["result"] == "ongoing"

    def test_finish_game(self, conn) -> None:
        repo = GameRepository(conn)
        gid = repo.create_game()
        repo.finish_game(gid, "user_win")
        assert repo.get_game(gid)["result"] == "user_win"

    def test_get_missing_returns_none(self, conn) -> None:
        assert GameRepository(conn).get_game(999) is None


class TestMoveRepository:
    def test_add_and_list_moves(self, conn) -> None:
        games = GameRepository(conn)
        moves = MoveRepository(conn)
        gid = games.create_game()
        moves.add_move(gid, 1, "user", 7, 7)
        moves.add_move(gid, 2, "ai", 8, 8, llm_commentary=None)
        rows = moves.list_moves(gid)
        assert len(rows) == 2
        assert rows[0]["position"] == "7,7"
        assert rows[0]["player"] == "user"
        assert rows[1]["move_number"] == 2

    def test_update_commentary(self, conn) -> None:
        games = GameRepository(conn)
        moves = MoveRepository(conn)
        gid = games.create_game()
        mid = moves.add_move(gid, 2, "ai", 8, 8)
        moves.update_commentary(mid, "你这一步意在连三……")
        rows = moves.list_moves(gid)
        assert rows[0]["llm_commentary"] == "你这一步意在连三……"


class TestSchema:
    def test_idempotent_connect(self, tmp_path) -> None:
        """重复连接（建表 IF NOT EXISTS）不报错。"""
        path = tmp_path / "test.db"
        conn1 = connect(path)
        conn1.close()
        conn2 = connect(path)
        conn2.close()

    def test_schema_tables_exist(self, conn) -> None:
        cur = conn.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = {row["name"] for row in cur.fetchall()}
        assert {"games", "moves"} <= tables
