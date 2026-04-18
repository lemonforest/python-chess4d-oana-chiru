"""Tests for :func:`chess4d.pieces.queen.queen_moves` (paper §3.8 Def 7).

Citations refer to Oana & Chiru, *A Mathematical Framework for
Four-Dimensional Chess*, MDPI AppliedMath 6(3):48, 2026
(DOI 10.3390/appliedmath6030048).

The queen generator is the union of the rook and bishop generators.
Each move has Hamming distance 1 or 2 from its origin (never 3 or 4 —
§3.8 Definition 7). Blocker semantics are slider-identical: a piece on
a ray stops further progress on that ray but does not affect other
directions.
"""

from __future__ import annotations

import itertools
import random

from hypothesis import given

from chess4d import Board4D, Color, Move4D, Piece, PieceType, Square4D
from chess4d.geometry import QUEEN_NEIGHBORS
from chess4d.pieces import queen_moves

from .conftest import squares_strategy


def _white_queen() -> Piece:
    return Piece(color=Color.WHITE, piece_type=PieceType.QUEEN)


def _black_queen() -> Piece:
    return Piece(color=Color.BLACK, piece_type=PieceType.QUEEN)


def _white_rook() -> Piece:
    return Piece(color=Color.WHITE, piece_type=PieceType.ROOK)


def _black_rook() -> Piece:
    return Piece(color=Color.BLACK, piece_type=PieceType.ROOK)


def _hamming(a: Square4D, b: Square4D) -> int:
    return sum(int(ai != bi) for ai, bi in zip(a, b))


# --- empty-board mobility ---------------------------------------------------


def test_queen_moves_empty_board_corner_is_70() -> None:
    """(0,0,0,0): 28 rook + 42 bishop = 70 on an empty board."""
    board = Board4D()
    moves = list(queen_moves(Square4D(0, 0, 0, 0), Color.WHITE, board))
    assert len(moves) == 70


def test_queen_moves_empty_board_matches_queen_neighbors_sample() -> None:
    """Generator cardinality matches ``QUEEN_NEIGHBORS`` on sampled squares."""
    board = Board4D()
    rng = random.Random(0)
    all_coords = [Square4D(*c) for c in itertools.product(range(8), repeat=4)]
    for sq in rng.sample(all_coords, 50):
        moves = list(queen_moves(sq, Color.WHITE, board))
        assert len(moves) == len(QUEEN_NEIGHBORS[sq]), sq


def test_queen_moves_from_field_matches_origin() -> None:
    board = Board4D()
    origin = Square4D(2, 4, 2, 4)
    for move in queen_moves(origin, Color.WHITE, board):
        assert move.from_sq == origin


# --- shape: Hamming 1 or 2 (§3.8 Def 7) -------------------------------------


def test_queen_moves_hamming_distance_1_or_2_from_center() -> None:
    """§3.8 Def 7: queen never makes a 3- or 4-axis move."""
    board = Board4D()
    origin = Square4D(3, 3, 3, 3)
    for move in queen_moves(origin, Color.WHITE, board):
        assert _hamming(move.from_sq, move.to_sq) in (1, 2)


@given(origin=squares_strategy)
def test_queen_moves_hamming_bound_property(origin: Square4D) -> None:
    """Hypothesis: from every origin, generated moves are Hamming ≤ 2."""
    board = Board4D()
    for move in queen_moves(origin, Color.WHITE, board):
        assert _hamming(move.from_sq, move.to_sq) in (1, 2)


# --- blockers and captures --------------------------------------------------


def test_queen_rook_ray_friendly_blocker_stops_axis_only() -> None:
    """Blocker on an axis ray kills that axis past it; diagonals unaffected."""
    board = Board4D()
    origin = Square4D(0, 0, 0, 0)
    board.place(origin, _white_queen())
    board.place(Square4D(3, 0, 0, 0), _white_rook())
    targets = {move.to_sq for move in queen_moves(origin, Color.WHITE, board)}
    # +x axis: blocked past (2,0,0,0)
    assert Square4D(1, 0, 0, 0) in targets
    assert Square4D(2, 0, 0, 0) in targets
    assert Square4D(3, 0, 0, 0) not in targets  # friendly — no capture
    assert Square4D(4, 0, 0, 0) not in targets
    # XY ++ diagonal: unaffected
    assert Square4D(1, 1, 0, 0) in targets
    assert Square4D(7, 7, 0, 0) in targets


def test_queen_bishop_ray_enemy_blocker_capture_and_stop() -> None:
    """Enemy on a diagonal ray is captured; ray stops past it. Axes unaffected."""
    board = Board4D()
    origin = Square4D(0, 0, 0, 0)
    board.place(origin, _white_queen())
    board.place(Square4D(2, 2, 0, 0), _black_rook())
    targets = {move.to_sq for move in queen_moves(origin, Color.WHITE, board)}
    # XY ++ diagonal: (1,1,...) free, (2,2,...) captured, (3,3,...) blocked.
    assert Square4D(1, 1, 0, 0) in targets
    assert Square4D(2, 2, 0, 0) in targets
    assert Square4D(3, 3, 0, 0) not in targets
    # +x axis unaffected
    assert Square4D(7, 0, 0, 0) in targets


def test_queen_friendly_blocker_on_diagonal_does_not_block_axis() -> None:
    """Independence check: diagonal and axis rays are separate."""
    board = Board4D()
    origin = Square4D(3, 3, 3, 3)
    board.place(origin, _white_queen())
    board.place(Square4D(4, 4, 3, 3), _white_queen())  # XY ++ blocker
    targets = {move.to_sq for move in queen_moves(origin, Color.WHITE, board)}
    # XY ++ past blocker: unreachable
    assert Square4D(5, 5, 3, 3) not in targets
    # +x axis (rook-type) unaffected
    assert Square4D(7, 3, 3, 3) in targets
    # ZW ++ diagonal unaffected
    assert Square4D(3, 3, 7, 7) in targets


# --- push/pop integration (smoke) -------------------------------------------


def test_push_and_pop_queen_diagonal_round_trip() -> None:
    board = Board4D()
    origin = Square4D(0, 0, 0, 0)
    target = Square4D(3, 3, 0, 0)
    board.place(origin, _white_queen())
    board.push(Move4D(from_sq=origin, to_sq=target))
    assert board.occupant(target) == _white_queen()
    assert board.occupant(origin) is None
    popped = board.pop()
    assert popped == Move4D(from_sq=origin, to_sq=target)
    assert board.occupant(origin) == _white_queen()
    assert board.occupant(target) is None


def test_push_and_pop_queen_axis_round_trip() -> None:
    board = Board4D()
    origin = Square4D(0, 0, 0, 0)
    target = Square4D(5, 0, 0, 0)
    board.place(origin, _white_queen())
    board.place(target, _black_queen())
    board.push(Move4D(from_sq=origin, to_sq=target))
    assert board.occupant(target) == _white_queen()
    board.pop()
    assert board.occupant(origin) == _white_queen()
    assert board.occupant(target) == _black_queen()
