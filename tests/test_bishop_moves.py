"""Tests for :func:`chess4d.pieces.bishop.bishop_moves` (paper §3.7, §3.8).

Citations refer to Oana & Chiru, *A Mathematical Framework for
Four-Dimensional Chess*, MDPI AppliedMath 6(3):48, 2026
(DOI 10.3390/appliedmath6030048).
"""

from __future__ import annotations

import itertools
import random

from hypothesis import given

from chess4d import Board4D, Color, PieceType, Piece, Square4D
from chess4d.geometry import BISHOP_NEIGHBORS
from chess4d.pieces import bishop_moves

from .conftest import squares_strategy


def _white_bishop() -> Piece:
    return Piece(color=Color.WHITE, piece_type=PieceType.BISHOP)


def _black_bishop() -> Piece:
    return Piece(color=Color.BLACK, piece_type=PieceType.BISHOP)


def _coords_differing(a: Square4D, b: Square4D) -> int:
    return sum(int(ai != bi) for ai, bi in zip(a, b))


# --- empty-board mobility ----------------------------------------------------


def test_bishop_moves_empty_board_corner_is_42() -> None:
    """(0,0,0,0): 42 moves on an empty board (one usable diagonal per plane)."""
    board = Board4D()
    moves = list(bishop_moves(Square4D(0, 0, 0, 0), Color.WHITE, board))
    assert len(moves) == 42


def test_bishop_moves_empty_board_matches_bishop_neighbors_sample() -> None:
    """Generator cardinality matches ``BISHOP_NEIGHBORS`` (sampled ~50 squares)."""
    board = Board4D()
    rng = random.Random(0)
    all_coords = [Square4D(*c) for c in itertools.product(range(8), repeat=4)]
    for sq in rng.sample(all_coords, 50):
        moves = list(bishop_moves(sq, Color.WHITE, board))
        assert len(moves) == len(BISHOP_NEIGHBORS[sq]), sq


def test_bishop_moves_are_axis_diagonal() -> None:
    """Every move changes exactly two coordinates by equal absolute value."""
    board = Board4D()
    origin = Square4D(3, 3, 3, 3)
    for move in bishop_moves(origin, Color.WHITE, board):
        assert _coords_differing(move.from_sq, move.to_sq) == 2
        deltas = [abs(a - b) for a, b in zip(move.from_sq, move.to_sq)]
        nonzero = [d for d in deltas if d != 0]
        assert len(nonzero) == 2
        assert nonzero[0] == nonzero[1]


def test_bishop_moves_from_matches_origin() -> None:
    board = Board4D()
    origin = Square4D(2, 4, 2, 4)
    for move in bishop_moves(origin, Color.WHITE, board):
        assert move.from_sq == origin


# --- parity (§3.8 Proposition 2(ii)) -----------------------------------------


def test_bishop_moves_preserve_parity_from_center() -> None:
    """§3.8 Prop 2(ii): every bishop move preserves parity."""
    board = Board4D()
    origin = Square4D(3, 3, 3, 3)
    for move in bishop_moves(origin, Color.WHITE, board):
        assert move.from_sq.parity() == move.to_sq.parity()


@given(origin=squares_strategy)
def test_bishop_moves_preserve_parity_property(origin: Square4D) -> None:
    """Hypothesis: bishop moves preserve parity from every origin."""
    board = Board4D()
    for move in bishop_moves(origin, Color.WHITE, board):
        assert move.from_sq.parity() == move.to_sq.parity()


# --- blockers and captures ---------------------------------------------------


def test_bishop_stops_at_friendly_blocker_on_plus_plus_diagonal() -> None:
    """XY ++ direction: friendly blocker at (2,2,0,0) kills the +/+ ray past it."""
    board = Board4D()
    origin = Square4D(0, 0, 0, 0)
    board.place(origin, _white_bishop())
    board.place(Square4D(2, 2, 0, 0), _white_bishop())
    targets = {move.to_sq for move in bishop_moves(origin, Color.WHITE, board)}
    assert Square4D(1, 1, 0, 0) in targets
    assert Square4D(2, 2, 0, 0) not in targets
    assert Square4D(3, 3, 0, 0) not in targets


def test_bishop_captures_opposing_blocker_and_stops() -> None:
    board = Board4D()
    origin = Square4D(0, 0, 0, 0)
    board.place(origin, _white_bishop())
    board.place(Square4D(2, 2, 0, 0), _black_bishop())
    targets = {move.to_sq for move in bishop_moves(origin, Color.WHITE, board)}
    assert Square4D(1, 1, 0, 0) in targets
    assert Square4D(2, 2, 0, 0) in targets  # capture
    assert Square4D(3, 3, 0, 0) not in targets


def test_bishop_blockers_on_different_planes_are_independent() -> None:
    """A blocker on the XY diagonal does not affect the ZW diagonal."""
    board = Board4D()
    origin = Square4D(3, 3, 3, 3)
    board.place(origin, _white_bishop())
    # XY ++ blocker at (4,4,3,3) kills that one ray (3 remaining targets on it).
    board.place(Square4D(4, 4, 3, 3), _white_bishop())
    targets = {move.to_sq for move in bishop_moves(origin, Color.WHITE, board)}
    # ZW ++ ray is untouched: (3,3,4,4), (3,3,5,5), (3,3,6,6), (3,3,7,7) are reachable.
    assert Square4D(3, 3, 7, 7) in targets
    # XY ++ past the blocker is not reachable.
    assert Square4D(5, 5, 3, 3) not in targets
