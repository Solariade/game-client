"""领域异常（由 common/errors.py 中 DomainError 派生）。"""

from __future__ import annotations

from app.common.errors import DomainError


class IllegalMoveError(DomainError):
    """非法落子：越界、已占用、非轮到该方等。"""


class GameOverError(DomainError):
    """对局已结束，不能继续落子。"""
