"""象棋规则单测：走法生成（perft 对齐 Pikafish 实测）、将军、合法过滤。"""

from __future__ import annotations

from app.core.xiangqi import rules
from app.core.xiangqi.fen import START_FEN, parse_fen


def grid_of(fen: str) -> list[list[str]]:
    return parse_fen(fen)[0]


class TestPerft:
    """起始局面逐层合法着法数，基准取自 Pikafish 实测输出。"""

    def test_perft_1(self) -> None:
        grid, side = parse_fen(START_FEN)
        assert rules.perft(grid, side, 1) == 44

    def test_perft_2(self) -> None:
        grid, side = parse_fen(START_FEN)
        assert rules.perft(grid, side, 2) == 1920

    # perft(3) = 79666、perft(4) = 3290240 同样与 Pikafish 一致，
    # 纯 Python 逐层展开较慢，按需在本地手工验证，不入默认套件。

    def test_start_move_count(self) -> None:
        grid, side = parse_fen(START_FEN)
        assert len(rules.legal_moves(grid, side)) == 44


class TestRook:
    def test_slide_and_own_block(self) -> None:
        grid = grid_of("4k4/9/9/9/9/9/9/9/9/R2K5 w - - 0 1")
        targets = set(rules.legal_targets(grid, 9, 0))
        assert targets == {(r, 0) for r in range(9)} | {(9, 1), (9, 2)}

    def test_blocked_by_own_pawn(self) -> None:
        grid = grid_of("4k4/9/9/9/9/9/9/9/P8/R2K5 w - - 0 1")
        assert rules.legal_targets(grid, 9, 0) == [(9, 1), (9, 2)]

    def test_capture_enemy(self) -> None:
        grid = grid_of("4k4/9/9/9/9/p8/9/9/9/R2K5 w - - 0 1")
        targets = rules.legal_targets(grid, 9, 0)
        assert (5, 0) in targets  # 吃黑卒
        assert (4, 0) not in targets  # 车不吃子不能越过黑卒


class TestCannon:
    def test_screen_capture(self) -> None:
        grid = grid_of("4k4/9/2n6/9/9/2p6/9/9/9/2C2K3 w - - 0 1")
        targets = rules.legal_targets(grid, 9, 2)
        # 阶段一滑行到炮架（黑卒）之前；隔炮架吃 (2,2) 黑马
        assert (8, 2) in targets and (7, 2) in targets and (6, 2) in targets
        assert (2, 2) in targets
        assert (5, 2) not in targets  # 炮架本身不可落
        assert (4, 2) not in targets and (3, 2) not in targets  # 炮架后空位不可落


class TestKnight:
    def test_leg_blocked_by_own_piece(self) -> None:
        grid = grid_of("3k5/9/9/9/9/9/9/9/9/1NB1K4 w - - 0 1")
        # 相 (9,2) 蹩了 (8,3) 方向的腿，只剩 (7,0)/(7,2)
        assert sorted(rules.legal_targets(grid, 9, 1)) == [(7, 0), (7, 2)]

    def test_edge_knight_no_wraparound(self) -> None:
        # 边线马：负索引若未拦截会回卷到对面行，此处应只有 3 个目标
        grid = grid_of("1n3k3/9/9/9/9/9/9/9/9/4K4 w - - 0 1")
        assert sorted(rules.legal_targets(grid, 0, 1)) == [(1, 3), (2, 0), (2, 2)]


class TestElephant:
    def test_eye_blocked_and_river(self) -> None:
        grid = grid_of("3k5/9/9/9/9/2B6/3P5/9/9/4K4 w - - 0 1")
        # (6,3) 红兵塞象眼挡住 (7,4)；(3,0)/(3,4) 过河不可去
        assert rules.legal_targets(grid, 5, 2) == [(7, 0)]


class TestAdvisorAndKing:
    def test_advisor_one_step_diag(self) -> None:
        grid = grid_of("3k5/9/9/9/9/9/9/9/9/3AK4 w - - 0 1")
        assert rules.legal_targets(grid, 9, 3) == [(8, 4)]

    def test_king_one_step_ortho(self) -> None:
        grid = grid_of("3k5/9/9/9/9/9/9/9/9/3AKA3 w - - 0 1")
        # 双仕占住左右，帅只能上进；仕只能上中
        assert rules.legal_targets(grid, 9, 4) == [(8, 4)]
        assert rules.legal_targets(grid, 9, 3) == [(8, 4)]
        assert rules.legal_targets(grid, 9, 5) == [(8, 4)]


class TestPawn:
    def test_red_uncrossed_forward_only(self) -> None:
        grid = grid_of("3k5/9/9/9/9/9/4P4/9/9/4K4 w - - 0 1")
        assert rules.legal_targets(grid, 6, 4) == [(5, 4)]

    def test_red_crossed_can_move_sideways(self) -> None:
        grid = grid_of("3k5/9/9/9/4P4/9/9/9/9/4K4 w - - 0 1")
        assert sorted(rules.legal_targets(grid, 4, 4)) == [(3, 4), (4, 3), (4, 5)]

    def test_red_at_last_rank_sideways_only(self) -> None:
        grid = grid_of("3kP4/9/9/9/9/9/9/9/9/4K4 w - - 0 1")
        assert sorted(rules.legal_targets(grid, 0, 4)) == [(0, 3), (0, 5)]

    def test_black_directions(self) -> None:
        grid = grid_of("3k5/9/9/2p6/9/9/9/9/9/4K4 w - - 0 1")
        assert rules.legal_targets(grid, 3, 2) == [(4, 2)]  # 未过河只进
        grid2 = grid_of("3k5/9/9/9/9/2p6/9/9/9/4K4 w - - 0 1")
        assert sorted(rules.legal_targets(grid2, 5, 2)) == [(5, 1), (5, 3), (6, 2)]


class TestCheck:
    def test_rook_check(self) -> None:
        grid = grid_of("3k5/9/9/9/3R5/9/9/9/9/4K4 w - - 0 1")
        assert rules.is_in_check(grid, rules.BLACK)
        assert not rules.is_in_check(grid, rules.RED)

    def test_cannon_check(self) -> None:
        grid = grid_of("3k5/9/3p5/9/3C5/9/9/9/9/4K4 w - - 0 1")
        assert rules.is_in_check(grid, rules.BLACK)

    def test_knight_check_and_leg_block(self) -> None:
        checked = grid_of("3k5/9/2N6/9/9/9/9/9/9/4K4 w - - 0 1")
        assert rules.is_in_check(checked, rules.BLACK)
        blocked = grid_of("3k5/2p6/2N6/9/9/9/9/9/9/4K4 w - - 0 1")  # (1,2) 黑卒蹩腿
        assert not rules.is_in_check(blocked, rules.BLACK)

    def test_kings_facing(self) -> None:
        facing = grid_of("4k4/9/9/9/9/9/9/9/9/4K4 w - - 0 1")
        assert rules.kings_facing(facing)
        assert rules.is_in_check(facing, rules.RED)
        assert rules.is_in_check(facing, rules.BLACK)
        screened = grid_of("4k4/9/9/9/9/4P4/9/9/9/4K4 w - - 0 1")
        assert not rules.kings_facing(screened)
        assert not rules.is_in_check(screened, rules.RED)


class TestLegality:
    def test_pinned_rook_cannot_leave_file(self) -> None:
        # 红车 (4,4) 在黑车与红帅之间被拴：横走露将非法，沿纵线可动/可吃
        grid = grid_of("3kr4/9/9/9/4R4/9/9/9/9/4K4 w - - 0 1")
        targets = rules.legal_targets(grid, 4, 4)
        assert (4, 3) not in targets
        assert (0, 4) in targets  # 吃掉拴住它的黑车

    def test_advisor_pinned_by_facing(self) -> None:
        # 双帅同列仅隔一仕 (8,4)：仕走开即对脸，故无合法着法；帅可横走
        grid = grid_of("4k4/9/9/9/9/9/9/9/4A4/4K4 w - - 0 1")
        assert rules.legal_targets(grid, 8, 4) == []
        assert sorted(rules.legal_targets(grid, 9, 4)) == [(9, 3), (9, 5)]

    def test_checkmate_position_has_no_moves(self) -> None:
        # 双马日字罩住黑将两侧，车在 (2,4) 将军
        grid = grid_of("4k4/9/2N1R1N2/9/9/9/9/9/9/3K5 b - - 0 1")
        assert rules.legal_moves(grid, rules.BLACK) == []
        assert rules.is_in_check(grid, rules.BLACK)

    def test_stalemate_position_has_no_moves(self) -> None:
        # 黑将不被将军但无路可走（困毙）
        grid = grid_of("3k5/2P1R4/9/9/9/9/9/9/9/4K4 b - - 0 1")
        assert rules.legal_moves(grid, rules.BLACK) == []
        assert not rules.is_in_check(grid, rules.BLACK)
