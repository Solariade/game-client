"""GameService 入库集成测试：两棋种的 game_type 与 position 格式。"""

from __future__ import annotations

import sqlite3

import pytest

from app.ai.base_engine import BaseEngine
from app.core.base_game import Move
from app.db.connection import connect
from app.db.repositories import GameRepository, MoveRepository
from app.services.commentary_service import CommentaryService
from app.services.game_service import GameService
from app.services.game_spec import make_gomoku_spec, make_xiangqi_spec


class ScriptedEngine(BaseEngine):
    """按脚本依次走子的桩引擎（元组 2 元=五子棋、4 元=象棋）。"""

    def __init__(self, moves: list[tuple[int, ...]]) -> None:
        self.moves = moves
        self.i = 0

    def search(self, game, depth: int, ai_color: int | None = None) -> Move:  # type: ignore[override]
        move = Move(*self.moves[self.i])
        self.i += 1
        return move


class FakeLLMClient:
    """按行吐固定分块的假 LLM。"""

    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.last_prompt: str | None = None

    def stream_commentary(self, prompt: str):
        self.last_prompt = prompt
        if self.fail:
            raise RuntimeError("模拟 LLM 故障")
        yield "红方中炮开局，"
        yield "直瞄中兵。"


@pytest.fixture
def conn(tmp_path) -> sqlite3.Connection:
    return connect(tmp_path / "test.db")


class TestGomokuPersistence:
    def test_positions_still_row_col(self, conn) -> None:
        games, moves = GameRepository(conn), MoveRepository(conn)
        service = GameService(
            engine=ScriptedEngine([(7, 8)]), game_repo=games, move_repo=moves, user_color=1
        )
        service.new_game()
        service.user_move(7, 7)
        service.take_ai_turn()
        assert games.get_game(service.game_id)["game_type"] == "gomoku"
        rows = moves.list_moves(service.game_id)
        assert [r["position"] for r in rows] == ["7,7", "7,8"]
        assert [r["player"] for r in rows] == ["user", "ai"]


class TestXiangqiPersistence:
    def test_game_type_and_iccs_positions(self, conn) -> None:
        games, moves = GameRepository(conn), MoveRepository(conn)
        service = GameService(
            engine=ScriptedEngine([(0, 7, 2, 6)]),
            game_repo=games,
            move_repo=moves,
            user_color=1,
            spec=make_xiangqi_spec(),
        )
        service.config.difficulty_name = "中等"
        service.new_game()
        game = games.get_game(service.game_id)
        assert game["game_type"] == "xiangqi"
        assert game["user_color"] == "red"
        assert game["difficulty"] == "中等"
        service.play_user_move(Move(7, 7, 7, 4))  # 炮二平五
        service.take_ai_turn()  # 马 8 进 7
        rows = moves.list_moves(service.game_id)
        assert [r["position"] for r in rows] == ["h2e2", "h9g7"]
        assert [r["player"] for r in rows] == ["user", "ai"]


class TestUndoPersistence:
    def test_undo_deletes_last_moves(self, conn) -> None:
        games, moves = GameRepository(conn), MoveRepository(conn)
        service = GameService(
            engine=ScriptedEngine([(0, 7, 2, 6)]),
            game_repo=games,
            move_repo=moves,
            user_color=1,
            spec=make_xiangqi_spec(),
        )
        service.new_game()
        service.play_user_move(Move(7, 7, 7, 4))
        service.take_ai_turn()
        assert len(moves.list_moves(service.game_id)) == 2

        assert service.undo_round() == 2
        assert moves.list_moves(service.game_id) == []

    def test_undo_after_game_over_clears_result(self, conn) -> None:
        games, moves = GameRepository(conn), MoveRepository(conn)
        service = GameService(
            spec=make_gomoku_spec(3), game_repo=games, move_repo=moves, user_color=1
        )
        service.new_game()
        for r in range(3):  # 填满 3×3 必平局
            for c in range(3):
                service.user_move(r, c)
        assert service.game_over is True
        assert games.get_game(service.game_id)["result"] == "draw"

        assert service.undo_round() == 1
        assert service.game_over is False
        assert games.get_game(service.game_id)["result"] == "ongoing"
        assert len(moves.list_moves(service.game_id)) == 8


class TestCommentaryService:
    def test_generate_streams_and_persists(self, conn) -> None:
        games, moves = GameRepository(conn), MoveRepository(conn)
        gid = games.create_game()
        mid = moves.add_move(gid, 2, "ai", "h9g7")
        service = CommentaryService(move_repo=moves)

        client = FakeLLMClient()
        chunks: list[str] = []
        done: list[str] = []
        full = service.generate(
            client, "提示词：局面……", move_id=mid, on_chunk=chunks.append, on_done=done.append
        )
        assert client.last_prompt == "提示词：局面……"
        assert chunks == ["红方中炮开局，", "直瞄中兵。"]
        assert full == "红方中炮开局，直瞄中兵。"
        assert done == [full]
        assert moves.list_moves(gid)[0]["llm_commentary"] == full

    def test_generate_degrades_on_llm_failure(self, conn) -> None:
        games, moves = GameRepository(conn), MoveRepository(conn)
        gid = games.create_game()
        service = CommentaryService(move_repo=moves)
        done: list[str] = []
        full = service.generate(FakeLLMClient(fail=True), "提示词", on_done=done.append)
        assert full  # 降级文案非空
        assert done == [full]
        assert moves.list_moves(gid) == []  # 没有 move_id，不落库
