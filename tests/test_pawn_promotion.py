"""Pawn promotion tests (paper §3.10, Definition 14).

When a pawn advances to the terminal rank of its forward axis, the
move is a promotion: the generator emits one :class:`Move4D` per
promotion target in ``{QUEEN, ROOK, BISHOP, KNIGHT}``, and :meth:`push`
replaces the pawn with the chosen piece. The pawn's ``pawn_axis`` is
cleared on the promoted piece (paper §3.3, §3.10 Def 14), and a
matching :meth:`pop` restores the original pawn — axis intact.
"""

from __future__ import annotations

import pytest

from chess4d import (
    Board4D,
    Color,
    IllegalMoveError,
    Move4D,
    PawnAxis,
    Piece,
    PieceType,
    Square4D,
    pawn_moves,
)


def _pawn(color: Color, axis: PawnAxis) -> Piece:
    return Piece(color=color, piece_type=PieceType.PAWN, pawn_axis=axis)


def _rook(color: Color) -> Piece:
    return Piece(color=color, piece_type=PieceType.ROOK)


_PROMO_TYPES: tuple[PieceType, ...] = (
    PieceType.QUEEN,
    PieceType.ROOK,
    PieceType.BISHOP,
    PieceType.KNIGHT,
)


# --- generator emits 4 moves on the promoting rank --------------------------


def test_white_y_pawn_promotion_forward_emits_four_moves() -> None:
    board = Board4D()
    origin = Square4D(3, 6, 0, 0)
    board.place(origin, _pawn(Color.WHITE, PawnAxis.Y))
    moves = list(pawn_moves(origin, Color.WHITE, board))
    # All four moves land on the same square.
    targets = {m.to_sq for m in moves}
    assert targets == {Square4D(3, 7, 0, 0)}
    # Promotions cover all four piece types.
    assert {m.promotion for m in moves} == set(_PROMO_TYPES)
    assert len(moves) == 4


def test_black_w_pawn_promotion_emits_four_moves() -> None:
    board = Board4D()
    origin = Square4D(3, 0, 0, 1)
    board.place(origin, _pawn(Color.BLACK, PawnAxis.W))
    moves = list(pawn_moves(origin, Color.BLACK, board))
    targets = {m.to_sq for m in moves}
    assert targets == {Square4D(3, 0, 0, 0)}
    assert {m.promotion for m in moves} == set(_PROMO_TYPES)


def test_capture_promotion_also_emits_four_moves() -> None:
    board = Board4D()
    origin = Square4D(3, 6, 0, 0)
    board.place(origin, _pawn(Color.WHITE, PawnAxis.Y))
    board.place(Square4D(3, 7, 0, 0), _rook(Color.WHITE))  # block forward
    board.place(Square4D(4, 7, 0, 0), _rook(Color.BLACK))
    moves = [m for m in pawn_moves(origin, Color.WHITE, board) if m.to_sq.x == 4]
    assert len(moves) == 4
    assert {m.promotion for m in moves} == set(_PROMO_TYPES)


def test_non_promoting_move_has_no_promotion_field() -> None:
    board = Board4D()
    origin = Square4D(3, 1, 0, 0)
    board.place(origin, _pawn(Color.WHITE, PawnAxis.Y))
    for m in pawn_moves(origin, Color.WHITE, board):
        assert m.promotion is None


# --- push applies promotion; pop restores the pawn --------------------------


@pytest.mark.parametrize("promo", _PROMO_TYPES)
def test_push_promotion_replaces_pawn_and_clears_axis(promo: PieceType) -> None:
    board = Board4D()
    origin = Square4D(3, 6, 0, 0)
    target = Square4D(3, 7, 0, 0)
    pawn = _pawn(Color.WHITE, PawnAxis.Y)
    board.place(origin, pawn)
    board.push(Move4D(origin, target, promotion=promo))
    placed = board.occupant(target)
    assert placed is not None
    assert placed.piece_type == promo
    assert placed.color == Color.WHITE
    assert placed.pawn_axis is None


@pytest.mark.parametrize("promo", _PROMO_TYPES)
def test_push_pop_promotion_restores_pawn_axis_intact(promo: PieceType) -> None:
    board = Board4D()
    origin = Square4D(3, 1, 0, 0)
    board.place(origin, _pawn(Color.BLACK, PawnAxis.Y))
    # walk the black Y-pawn toward promotion in a single 1-step jump by re-placing.
    # Simpler: put pawn on rank 1 for black (promotion target).
    board = Board4D()
    origin = Square4D(3, 1, 5, 5)
    target = Square4D(3, 0, 5, 5)
    pawn = _pawn(Color.BLACK, PawnAxis.Y)
    board.place(origin, pawn)
    board.push(Move4D(origin, target, promotion=promo))
    board.pop()
    restored = board.occupant(origin)
    assert restored == pawn  # color, piece_type, pawn_axis all equal


def test_promotion_capture_push_pop_restores_both_pawn_and_enemy() -> None:
    board = Board4D()
    origin = Square4D(3, 6, 0, 0)
    target = Square4D(4, 7, 0, 0)
    pawn = _pawn(Color.WHITE, PawnAxis.Y)
    enemy = _rook(Color.BLACK)
    board.place(origin, pawn)
    board.place(target, enemy)
    board.push(Move4D(origin, target, promotion=PieceType.QUEEN))
    assert board.occupant(target) == Piece(Color.WHITE, PieceType.QUEEN)
    board.pop()
    assert board.occupant(origin) == pawn
    assert board.occupant(target) == enemy


# --- rejection paths --------------------------------------------------------


def test_push_rejects_missing_promotion_on_promoting_rank() -> None:
    board = Board4D()
    origin = Square4D(3, 6, 0, 0)
    board.place(origin, _pawn(Color.WHITE, PawnAxis.Y))
    with pytest.raises(IllegalMoveError):
        board.push(Move4D(origin, Square4D(3, 7, 0, 0)))


def test_push_rejects_promotion_to_pawn() -> None:
    board = Board4D()
    origin = Square4D(3, 6, 0, 0)
    board.place(origin, _pawn(Color.WHITE, PawnAxis.Y))
    with pytest.raises(IllegalMoveError):
        board.push(Move4D(origin, Square4D(3, 7, 0, 0), promotion=PieceType.PAWN))


def test_push_rejects_promotion_to_king() -> None:
    board = Board4D()
    origin = Square4D(3, 6, 0, 0)
    board.place(origin, _pawn(Color.WHITE, PawnAxis.Y))
    with pytest.raises(IllegalMoveError):
        board.push(Move4D(origin, Square4D(3, 7, 0, 0), promotion=PieceType.KING))


def test_push_rejects_promotion_on_non_promoting_rank() -> None:
    board = Board4D()
    origin = Square4D(3, 1, 0, 0)
    board.place(origin, _pawn(Color.WHITE, PawnAxis.Y))
    with pytest.raises(IllegalMoveError):
        board.push(Move4D(origin, Square4D(3, 2, 0, 0), promotion=PieceType.QUEEN))


def test_promoted_queen_moves_as_queen_after_push() -> None:
    """Smoke: after promotion, the new queen can use queen geometry."""
    board = Board4D()
    origin = Square4D(0, 6, 0, 0)
    promo_sq = Square4D(0, 7, 0, 0)
    board.place(origin, _pawn(Color.WHITE, PawnAxis.Y))
    board.push(Move4D(origin, promo_sq, promotion=PieceType.QUEEN))
    # Queen slides along y back to y=0.
    board.push(Move4D(promo_sq, Square4D(0, 0, 0, 0)))
    queen_now = board.occupant(Square4D(0, 0, 0, 0))
    assert queen_now is not None
    assert queen_now.piece_type == PieceType.QUEEN
