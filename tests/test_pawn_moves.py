"""Pawn move-generation and execution tests (paper §3.10, Def 12-13).

Covers:

* one-step forward emission,
* two-step-from-start-rank emission,
* forward blocked by any piece (friendly or enemy),
* captures require an enemy piece,
* captures cannot target empty or friendly squares,
* Y↔W axis parameterization,
* white/black direction parameterization,
* push/pop round-trips of every case above (undo-stack shape).

Promotion is exercised separately in ``test_pawn_promotion.py``.
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


# --- generator emissions ----------------------------------------------------


def test_white_y_pawn_on_start_rank_yields_one_and_two_step() -> None:
    board = Board4D()
    origin = Square4D(3, 1, 4, 5)
    board.place(origin, _pawn(Color.WHITE, PawnAxis.Y))
    moves = list(pawn_moves(origin, Color.WHITE, board))
    targets = {m.to_sq for m in moves}
    assert Square4D(3, 2, 4, 5) in targets
    assert Square4D(3, 3, 4, 5) in targets
    assert len(moves) == 2


def test_black_y_pawn_on_start_rank_moves_downward() -> None:
    board = Board4D()
    origin = Square4D(3, 6, 4, 5)
    board.place(origin, _pawn(Color.BLACK, PawnAxis.Y))
    targets = {m.to_sq for m in pawn_moves(origin, Color.BLACK, board)}
    assert targets == {Square4D(3, 5, 4, 5), Square4D(3, 4, 4, 5)}


def test_white_w_pawn_advances_along_w_axis() -> None:
    board = Board4D()
    origin = Square4D(3, 4, 5, 1)
    board.place(origin, _pawn(Color.WHITE, PawnAxis.W))
    targets = {m.to_sq for m in pawn_moves(origin, Color.WHITE, board)}
    assert targets == {Square4D(3, 4, 5, 2), Square4D(3, 4, 5, 3)}


def test_past_start_rank_yields_one_step_only() -> None:
    board = Board4D()
    origin = Square4D(3, 4, 2, 2)
    board.place(origin, _pawn(Color.WHITE, PawnAxis.Y))
    moves = list(pawn_moves(origin, Color.WHITE, board))
    assert [m.to_sq for m in moves] == [Square4D(3, 5, 2, 2)]


def test_forward_blocked_by_friendly_piece() -> None:
    board = Board4D()
    origin = Square4D(3, 1, 0, 0)
    board.place(origin, _pawn(Color.WHITE, PawnAxis.Y))
    board.place(Square4D(3, 2, 0, 0), _rook(Color.WHITE))
    assert list(pawn_moves(origin, Color.WHITE, board)) == []


def test_forward_blocked_by_enemy_piece_no_capture_on_forward() -> None:
    """Pawns do NOT capture on their forward square (classical chess)."""
    board = Board4D()
    origin = Square4D(3, 1, 0, 0)
    board.place(origin, _pawn(Color.WHITE, PawnAxis.Y))
    board.place(Square4D(3, 2, 0, 0), _rook(Color.BLACK))
    assert list(pawn_moves(origin, Color.WHITE, board)) == []


def test_two_step_blocked_by_intermediate() -> None:
    board = Board4D()
    origin = Square4D(3, 1, 0, 0)
    board.place(origin, _pawn(Color.WHITE, PawnAxis.Y))
    # Block one-step (which also blocks two-step).
    board.place(Square4D(3, 2, 0, 0), _rook(Color.BLACK))
    assert list(pawn_moves(origin, Color.WHITE, board)) == []


def test_two_step_blocked_at_target_only() -> None:
    """One-step is clear, but the two-step target is blocked — only
    the one-step is emitted."""
    board = Board4D()
    origin = Square4D(3, 1, 0, 0)
    board.place(origin, _pawn(Color.WHITE, PawnAxis.Y))
    board.place(Square4D(3, 3, 0, 0), _rook(Color.BLACK))
    targets = {m.to_sq for m in pawn_moves(origin, Color.WHITE, board)}
    assert targets == {Square4D(3, 2, 0, 0)}


# --- capture emissions ------------------------------------------------------


def test_capture_requires_enemy() -> None:
    board = Board4D()
    origin = Square4D(3, 2, 0, 0)
    board.place(origin, _pawn(Color.WHITE, PawnAxis.Y))
    # No occupant on diagonals → no captures.
    for m in pawn_moves(origin, Color.WHITE, board):
        assert m.to_sq == Square4D(3, 3, 0, 0)  # only forward


def test_capture_on_xy_diagonal() -> None:
    board = Board4D()
    origin = Square4D(3, 2, 0, 0)
    board.place(origin, _pawn(Color.WHITE, PawnAxis.Y))
    board.place(Square4D(2, 3, 0, 0), _rook(Color.BLACK))
    board.place(Square4D(4, 3, 0, 0), _rook(Color.BLACK))
    targets = {m.to_sq for m in pawn_moves(origin, Color.WHITE, board)}
    assert Square4D(2, 3, 0, 0) in targets
    assert Square4D(4, 3, 0, 0) in targets


def test_w_pawn_captures_on_xw_diagonal() -> None:
    board = Board4D()
    origin = Square4D(3, 0, 0, 2)
    board.place(origin, _pawn(Color.WHITE, PawnAxis.W))
    board.place(Square4D(4, 0, 0, 3), _rook(Color.BLACK))
    targets = {m.to_sq for m in pawn_moves(origin, Color.WHITE, board)}
    assert Square4D(4, 0, 0, 3) in targets


def test_capture_does_not_include_friendly() -> None:
    board = Board4D()
    origin = Square4D(3, 2, 0, 0)
    board.place(origin, _pawn(Color.WHITE, PawnAxis.Y))
    board.place(Square4D(2, 3, 0, 0), _rook(Color.WHITE))
    for m in pawn_moves(origin, Color.WHITE, board):
        assert m.to_sq != Square4D(2, 3, 0, 0)


def test_capture_boundary_clip() -> None:
    """Pawn on x=0 has only one diagonal capture available (x=+1 side)."""
    board = Board4D()
    origin = Square4D(0, 2, 0, 0)
    board.place(origin, _pawn(Color.WHITE, PawnAxis.Y))
    board.place(Square4D(1, 3, 0, 0), _rook(Color.BLACK))
    capture_targets = [
        m.to_sq for m in pawn_moves(origin, Color.WHITE, board) if m.to_sq.y == 3 and m.to_sq.x != 0
    ]
    assert capture_targets == [Square4D(1, 3, 0, 0)]


def test_pawn_generator_requires_pawn_at_origin() -> None:
    board = Board4D()
    origin = Square4D(0, 0, 0, 0)
    board.place(origin, _rook(Color.WHITE))
    with pytest.raises(ValueError):
        list(pawn_moves(origin, Color.WHITE, board))


def test_pawn_generator_requires_piece_at_origin() -> None:
    board = Board4D()
    with pytest.raises(ValueError):
        list(pawn_moves(Square4D(0, 0, 0, 0), Color.WHITE, board))


# --- push / pop round-trips -------------------------------------------------


def test_push_pop_one_step() -> None:
    board = Board4D()
    origin = Square4D(3, 1, 0, 0)
    before = {origin: _pawn(Color.WHITE, PawnAxis.Y)}
    board.place(origin, _pawn(Color.WHITE, PawnAxis.Y))
    board.push(Move4D(origin, Square4D(3, 2, 0, 0)))
    assert board.occupant(Square4D(3, 2, 0, 0)) == _pawn(Color.WHITE, PawnAxis.Y)
    board.pop()
    assert {sq: board.occupant(sq) for sq in before} == before
    assert board.occupant(Square4D(3, 2, 0, 0)) is None


def test_push_pop_two_step() -> None:
    board = Board4D()
    origin = Square4D(3, 1, 0, 0)
    board.place(origin, _pawn(Color.WHITE, PawnAxis.Y))
    board.push(Move4D(origin, Square4D(3, 3, 0, 0)))
    assert board.occupant(Square4D(3, 3, 0, 0)) == _pawn(Color.WHITE, PawnAxis.Y)
    board.pop()
    assert board.occupant(origin) == _pawn(Color.WHITE, PawnAxis.Y)


def test_push_pop_capture_restores_enemy() -> None:
    board = Board4D()
    origin = Square4D(3, 2, 0, 0)
    target = Square4D(4, 3, 0, 0)
    pawn = _pawn(Color.WHITE, PawnAxis.Y)
    enemy = _rook(Color.BLACK)
    board.place(origin, pawn)
    board.place(target, enemy)
    board.push(Move4D(origin, target))
    assert board.occupant(target) == pawn
    assert board.occupant(origin) is None
    board.pop()
    assert board.occupant(origin) == pawn
    assert board.occupant(target) == enemy


def test_push_rejects_non_pseudo_legal_pawn_move() -> None:
    board = Board4D()
    origin = Square4D(3, 2, 0, 0)
    board.place(origin, _pawn(Color.WHITE, PawnAxis.Y))
    # (3,2)->(5,2) is not a pawn move at all.
    with pytest.raises(IllegalMoveError):
        board.push(Move4D(origin, Square4D(5, 2, 0, 0)))


def test_push_rejects_forward_onto_enemy() -> None:
    board = Board4D()
    origin = Square4D(3, 1, 0, 0)
    board.place(origin, _pawn(Color.WHITE, PawnAxis.Y))
    board.place(Square4D(3, 2, 0, 0), _rook(Color.BLACK))
    with pytest.raises(IllegalMoveError):
        board.push(Move4D(origin, Square4D(3, 2, 0, 0)))


def test_push_rejects_capture_onto_empty() -> None:
    board = Board4D()
    origin = Square4D(3, 2, 0, 0)
    board.place(origin, _pawn(Color.WHITE, PawnAxis.Y))
    with pytest.raises(IllegalMoveError):
        board.push(Move4D(origin, Square4D(4, 3, 0, 0)))


def test_push_rejects_capture_onto_friendly() -> None:
    board = Board4D()
    origin = Square4D(3, 2, 0, 0)
    board.place(origin, _pawn(Color.WHITE, PawnAxis.Y))
    board.place(Square4D(4, 3, 0, 0), _rook(Color.WHITE))
    with pytest.raises(IllegalMoveError):
        board.push(Move4D(origin, Square4D(4, 3, 0, 0)))


def test_push_rejects_two_step_when_blocked_at_intermediate() -> None:
    board = Board4D()
    origin = Square4D(3, 1, 0, 0)
    board.place(origin, _pawn(Color.WHITE, PawnAxis.Y))
    board.place(Square4D(3, 2, 0, 0), _rook(Color.WHITE))
    with pytest.raises(IllegalMoveError):
        board.push(Move4D(origin, Square4D(3, 3, 0, 0)))


@pytest.mark.parametrize(
    "color,axis,origin,target",
    [
        (Color.WHITE, PawnAxis.Y, Square4D(3, 1, 0, 0), Square4D(3, 2, 0, 0)),
        (Color.BLACK, PawnAxis.Y, Square4D(3, 6, 0, 0), Square4D(3, 5, 0, 0)),
        (Color.WHITE, PawnAxis.W, Square4D(0, 0, 0, 1), Square4D(0, 0, 0, 2)),
        (Color.BLACK, PawnAxis.W, Square4D(0, 0, 0, 6), Square4D(0, 0, 0, 5)),
    ],
)
def test_push_pop_parameterized_on_color_and_axis(
    color: Color, axis: PawnAxis, origin: Square4D, target: Square4D
) -> None:
    board = Board4D()
    pawn = _pawn(color, axis)
    board.place(origin, pawn)
    board.push(Move4D(origin, target))
    assert board.occupant(target) == pawn
    assert board.occupant(origin) is None
    board.pop()
    assert board.occupant(origin) == pawn
    assert board.occupant(target) is None
