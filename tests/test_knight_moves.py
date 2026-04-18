"""Tests for :func:`chess4d.pieces.knight.knight_moves` (paper §3.8).

Citations refer to Oana & Chiru, *A Mathematical Framework for
Four-Dimensional Chess*, MDPI AppliedMath 6(3):48, 2026
(DOI 10.3390/appliedmath6030048).

The knight is a leaper: it jumps directly to its target, so pieces on
intermediate squares never block the move. Standard friendly-blocks /
enemy-captures semantics apply only at the target. §3.8 Prop 2(iii):
every knight move flips parity.
"""

from __future__ import annotations

import itertools
import random

from hypothesis import given

from chess4d import Board4D, Color, Move4D, Piece, PieceType, Square4D
from chess4d.geometry import KNIGHT_NEIGHBORS
from chess4d.pieces import knight_moves

from .conftest import squares_strategy


def _white_knight() -> Piece:
    return Piece(color=Color.WHITE, piece_type=PieceType.KNIGHT)


def _black_knight() -> Piece:
    return Piece(color=Color.BLACK, piece_type=PieceType.KNIGHT)


def _white_rook() -> Piece:
    return Piece(color=Color.WHITE, piece_type=PieceType.ROOK)


def _black_rook() -> Piece:
    return Piece(color=Color.BLACK, piece_type=PieceType.ROOK)


# --- empty-board mobility ---------------------------------------------------


def test_knight_moves_empty_board_interior_has_48() -> None:
    """§3.8 Thm 3: interior knight mobility is uniformly 48."""
    board = Board4D()
    moves = list(knight_moves(Square4D(3, 3, 3, 3), Color.WHITE, board))
    assert len(moves) == 48


def test_knight_moves_empty_board_corner_has_12() -> None:
    """(0,0,0,0): only +2,+1 sign combinations reach in bounds. 4 × 3 = 12."""
    board = Board4D()
    moves = list(knight_moves(Square4D(0, 0, 0, 0), Color.WHITE, board))
    assert len(moves) == 12


def test_knight_moves_empty_board_matches_neighbors_sample() -> None:
    """Generator cardinality matches ``KNIGHT_NEIGHBORS`` on sampled squares."""
    board = Board4D()
    rng = random.Random(0)
    all_coords = [Square4D(*c) for c in itertools.product(range(8), repeat=4)]
    for sq in rng.sample(all_coords, 50):
        moves = list(knight_moves(sq, Color.WHITE, board))
        assert len(moves) == len(KNIGHT_NEIGHBORS[sq]), sq


def test_knight_moves_from_matches_origin() -> None:
    board = Board4D()
    origin = Square4D(2, 4, 2, 4)
    for move in knight_moves(origin, Color.WHITE, board):
        assert move.from_sq == origin


# --- shape: permutation of (±2, ±1, 0, 0) -----------------------------------


def test_knight_moves_deltas_match_definition_8() -> None:
    """§3.8 Def 8: every knight delta is a permutation of (±2, ±1, 0, 0)."""
    board = Board4D()
    origin = Square4D(3, 3, 3, 3)
    for move in knight_moves(origin, Color.WHITE, board):
        sorted_abs = sorted(abs(a - b) for a, b in zip(move.from_sq, move.to_sq))
        assert sorted_abs == [0, 0, 1, 2], move


# --- parity (§3.8 Proposition 2(iii)) ---------------------------------------


@given(origin=squares_strategy)
def test_knight_moves_always_flip_parity_property(origin: Square4D) -> None:
    """Hypothesis: knight moves flip parity from every origin."""
    board = Board4D()
    for move in knight_moves(origin, Color.WHITE, board):
        assert move.from_sq.parity() != move.to_sq.parity()


# --- leaper: intermediate squares do NOT block ------------------------------


def test_knight_leaper_jumps_over_adjacent_piece() -> None:
    """A knight move (0,0,0,0)→(2,1,0,0) is *not* blocked by a piece on (1,0,0,0)."""
    board = Board4D()
    origin = Square4D(0, 0, 0, 0)
    board.place(origin, _white_knight())
    board.place(Square4D(1, 0, 0, 0), _white_rook())  # "intermediate" — irrelevant
    board.place(Square4D(1, 1, 0, 0), _black_rook())  # another "intermediate" — irrelevant
    targets = {move.to_sq for move in knight_moves(origin, Color.WHITE, board)}
    assert Square4D(2, 1, 0, 0) in targets
    assert Square4D(1, 2, 0, 0) in targets


# --- blockers and captures at the target ------------------------------------


def test_knight_does_not_land_on_friendly_piece() -> None:
    board = Board4D()
    origin = Square4D(3, 3, 3, 3)
    board.place(origin, _white_knight())
    board.place(Square4D(5, 4, 3, 3), _white_rook())  # friendly on a reachable square
    targets = {move.to_sq for move in knight_moves(origin, Color.WHITE, board)}
    assert Square4D(5, 4, 3, 3) not in targets


def test_knight_captures_enemy_piece_at_target() -> None:
    board = Board4D()
    origin = Square4D(3, 3, 3, 3)
    board.place(origin, _white_knight())
    board.place(Square4D(5, 4, 3, 3), _black_rook())
    targets = {move.to_sq for move in knight_moves(origin, Color.WHITE, board)}
    assert Square4D(5, 4, 3, 3) in targets


# --- push/pop integration ---------------------------------------------------


def test_push_and_pop_knight_round_trip() -> None:
    board = Board4D()
    origin = Square4D(3, 3, 3, 3)
    target = Square4D(5, 4, 3, 3)
    board.place(origin, _white_knight())
    board.push(Move4D(from_sq=origin, to_sq=target))
    assert board.occupant(target) == _white_knight()
    assert board.occupant(origin) is None
    board.pop()
    assert board.occupant(origin) == _white_knight()
    assert board.occupant(target) is None


def test_push_knight_captures_and_pop_restores() -> None:
    board = Board4D()
    origin = Square4D(3, 3, 3, 3)
    target = Square4D(5, 4, 3, 3)
    board.place(origin, _white_knight())
    board.place(target, _black_knight())
    board.push(Move4D(from_sq=origin, to_sq=target))
    assert board.occupant(target) == _white_knight()
    board.pop()
    assert board.occupant(origin) == _white_knight()
    assert board.occupant(target) == _black_knight()


def test_push_knight_over_intermediate_pieces_works() -> None:
    """Leaper: intermediate pieces are irrelevant during push validation too."""
    board = Board4D()
    origin = Square4D(0, 0, 0, 0)
    target = Square4D(2, 1, 0, 0)
    board.place(origin, _white_knight())
    board.place(Square4D(1, 0, 0, 0), _white_rook())
    board.place(Square4D(1, 1, 0, 0), _black_rook())
    board.push(Move4D(from_sq=origin, to_sq=target))
    assert board.occupant(target) == _white_knight()
