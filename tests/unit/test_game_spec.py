"""GameSpec 与参数化 GameService 单测（无 DB）：象棋注入路径全走一遍。"""

from __future__ import annotations

import pytest

from app.ai.base_engine import BaseEngine
from app.core.base_game import Move
from app.core.gomoku.board import GomokuBoard
from app.core.xiangqi.board import XiangqiBoard
from app.services.game_service import GameService
from app.services.game_spec import GameServiceFactory, make_gomoku_spec, make_xiangqi_spec


class ScriptedEngine(BaseEngine):
    """按脚本依次走子的桩引擎（元组 2 元=五子棋、4 元=象棋）。"""

    def __init__(self, moves: list[tuple[int, ...]]) -> None:
        self.moves = moves
        self.i = 0
        self.last_color: int | None = None
        self.last_depth: int | None = None

    def search(self, game, depth: int, ai_color: int | None = None) -> Move:  # type: ignore[override]
        self.last_color = ai_color
        self.last_depth = depth
        move = Move(*self.moves[self.i])
        self.i += 1
        return move


# 炮二平五（红）与黑马 8 进 7（黑）的 Move 表示
H2E2 = (7, 7, 7, 4)
H9G7 = (0, 7, 2, 6)


class TestGameSpec:
    def test_gomoku_spec_mappings(self) -> None:
        spec = make_gomoku_spec()
        board = spec.game_factory()
        assert isinstance(board, GomokuBoard)
        assert spec.game_type == "gomoku"
        assert spec.user_color_name(1) == "black"
        assert spec.user_color_name(-1) == "white"
        assert spec.position_text(Move(7, 7)) == "7,7"
        assert spec.color_display(1) == "黑"
        assert spec.color_display(-1) == "白"

    def test_gomoku_spec_honors_board_size(self) -> None:
        assert make_gomoku_spec(3).game_factory().size == 3

    def test_xiangqi_spec_mappings(self) -> None:
        spec = make_xiangqi_spec()
        assert isinstance(spec.game_factory(), XiangqiBoard)
        assert spec.game_type == "xiangqi"
        assert spec.user_color_name(1) == "red"
        assert spec.user_color_name(-1) == "black"
        assert spec.position_text(Move(*H2E2)) == "h2e2"
        assert spec.color_display(1) == "红"
        assert spec.color_display(-1) == "黑"


class TestGameServiceDefaultSpec:
    def test_no_spec_falls_back_to_gomoku(self) -> None:
        service = GameService(board=GomokuBoard())
        assert service.spec.game_type == "gomoku"
        service.new_game()
        assert isinstance(service.board, GomokuBoard)
        assert service.board.size == 15

    def test_no_spec_uses_board_size(self) -> None:
        service = GameService(board=GomokuBoard(size=3))
        service.new_game()
        assert service.board.size == 3  # 重建棋盘保持原尺寸


class TestXiangqiGameService:
    def make_service(self, moves: list[tuple[int, ...]]) -> GameService:
        return GameService(engine=ScriptedEngine(moves), user_color=1, spec=make_xiangqi_spec())

    def test_new_game_builds_xiangqi_board(self) -> None:
        service = self.make_service([])
        service.new_game()
        assert isinstance(service.board, XiangqiBoard)
        assert service.user_turn is True  # 红先，用户执红

    def test_user_and_ai_turn_flow(self) -> None:
        service = self.make_service([H9G7])
        r1 = service.play_user_move(Move(*H2E2))
        assert (r1.move.row, r1.move.col, r1.move.to_row, r1.move.to_col) == H2E2
        assert r1.color == 1
        assert r1.game_over is False
        assert service.user_turn is False
        r2 = service.take_ai_turn()
        assert (r2.move.to_row, r2.move.to_col) == (2, 6)
        assert r2.color == -1
        assert service.user_turn is True
        assert service.engine.last_color == -1  # type: ignore[attr-defined]

    def test_user_move_rejects_illegal(self) -> None:
        from app.core.exceptions import IllegalMoveError

        service = self.make_service([])
        with pytest.raises(IllegalMoveError):
            service.play_user_move(Move(0, 0, 0, 1))  # 红方行棋：动对方的车

    def test_suggest_for_user_returns_legal_move(self) -> None:
        service = self.make_service([H2E2])
        assert service.suggest_for_user() == Move(*H2E2)
        assert service.engine.last_color == 1  # type: ignore[attr-defined]
        assert service.engine.last_depth == 4  # type: ignore[attr-defined]

    def test_suggest_for_user_filters_unplayable(self) -> None:
        # 引擎返回动黑车的着法（红方行棋）→ is_playable 过滤为 None
        service = self.make_service([(0, 0, 0, 1)])
        assert service.suggest_for_user() is None

    def test_suggest_for_user_none_when_not_user_turn(self) -> None:
        service = self.make_service([])
        service.play_user_move(Move(*H2E2))
        assert service.suggest_for_user() is None  # 轮黑（AI）

    def test_win_line_is_none_for_xiangqi(self) -> None:
        service = self.make_service([H9G7])
        result = service.play_user_move(Move(*H2E2))
        assert result.win_line is None  # 象棋无连线概念（终局展示走 M14）

    def test_take_ai_turn_carries_engine_eval(self) -> None:
        from app.ai.xiangqi.engine import EngineEval

        class EvalEngine(ScriptedEngine):
            def __init__(self, moves: list[tuple[int, ...]], eval_result: EngineEval) -> None:
                super().__init__(moves)
                self.last_eval = eval_result

        ev = EngineEval(bestmove="h9g7", score_cp=-42)
        service = GameService(engine=EvalEngine([H9G7], ev), user_color=1, spec=make_xiangqi_spec())
        service.play_user_move(Move(*H2E2))
        assert service.take_ai_turn().engine_eval is ev

    def test_take_ai_turn_eval_none_for_plain_engine(self) -> None:
        # 无 last_eval 属性的引擎（五子棋式桩）不报错，engine_eval 为 None
        service = self.make_service([H9G7])
        service.play_user_move(Move(*H2E2))
        assert service.take_ai_turn().engine_eval is None


class TestGameServiceFactory:
    def make_factory(self, xiangqi_available: bool = True) -> GameServiceFactory:
        return GameServiceFactory(
            engines={"gomoku": ScriptedEngine([]), "xiangqi": FakeXiangqiEngine(xiangqi_available)}
        )

    def test_create_gomoku(self) -> None:
        service = self.make_factory().create("gomoku")
        assert service.spec.game_type == "gomoku"
        service.new_game()
        assert isinstance(service.board, GomokuBoard)

    def test_create_xiangqi(self) -> None:
        service = self.make_factory().create("xiangqi", user_color=1)
        assert service.spec.game_type == "xiangqi"
        assert service.user_color == 1
        service.new_game()
        assert isinstance(service.board, XiangqiBoard)

    def test_unknown_game_type_raises(self) -> None:
        with pytest.raises(ValueError):
            self.make_factory().create("reversi")

    def test_available_games_excludes_missing_engine(self) -> None:
        factory = self.make_factory(xiangqi_available=False)
        assert factory.available_games() == ["gomoku"]
        with pytest.raises(ValueError):
            factory.create("xiangqi")

    def test_default_game_prefers_xiangqi(self) -> None:
        """引擎齐全时启动默认象棋。"""
        assert self.make_factory(xiangqi_available=True).default_game == "xiangqi"

    def test_default_game_falls_back_to_gomoku(self) -> None:
        """Pikafish 缺失时回落五子棋。"""
        assert self.make_factory(xiangqi_available=False).default_game == "gomoku"

    def test_shutdown_quits_subprocess_engines(self) -> None:
        engine = FakeXiangqiEngine(True)
        plain = ScriptedEngine([])
        GameServiceFactory(engines={"gomoku": plain, "xiangqi": engine}).shutdown()
        assert engine.quit_calls == 1  # 纯计算引擎（无 quit）不受影响


class FakeXiangqiEngine(ScriptedEngine):
    """带 available/quit 的象棋桩引擎。"""

    def __init__(self, available: bool) -> None:
        super().__init__([])
        self.available = available
        self.quit_calls = 0

    def quit(self) -> None:
        self.quit_calls += 1
