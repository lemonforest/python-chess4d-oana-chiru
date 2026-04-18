"""Tests for :func:`chess4d.pieces.king.king_moves` (paper §3.9 Def 9).

Citations refer to Oana & Chiru, *A Mathematical Framework for
Four-Dimensional Chess*, MDPI AppliedMath 6(3):48, 2026
(DOI 10.3390/appliedmath6030048).

The king is a Chebyshev-1 leaper: every move is to an immediately
adjacent square (no intermediates). Standard friendly-blocks / enemy-
captures semantics apply. Castling (§3.9 Def 10) requires castling-
rights state and is deferred to a later phase.
"""

from __future__ import annotations

import itertools
import random

from chess4d import Board4D, Color, Move4D, Piece, PieceType, Square4D
from chess4d.geometry import KING_NEIGHBORS
from chess4d.pieces import king_moves


def _white_king() -> Piece:
    return Piece(color=Color.WHITE, piece_type=PieceType.KING)


def _black_king() -> Piece:
    return Piece(color=Color.BLACK, piece_type=PieceType.KING)


def _white_rook() -> Piece:
    return Piece(color=Color.WHITE, piece_type=PieceType.ROOK)


def _black_rook() -> Piece:
    return Piece(color=Color.BLACK, piece_type=PieceType.ROOK)


# --- empty-board mobility ---------------------------------------------------


def test_king_moves_empty_board_interior_is_80() -> None:
    """§3.9 Def 9 + §3.2 Lemma 1: interior king has 80 empty-board moves."""
    board = Board4D()
    moves = list(king_moves(Square4D(3, 3, 3, 3), Color.WHITE, board))
    assert len(moves) == 80


def test_king_moves_empty_board_corner_is_15() -> None:
    """(0,0,0,0): 2^4 − 1 = 15 (only 0/+1 per axis)."""
    board = Board4D()
    moves = list(king_moves(Square4D(0, 0, 0, 0), Color.WHITE, board))
    assert len(moves) == 15


def test_king_moves_empty_board_matches_neighbors_sample() -> None:
    board = Board4D()
    rng = random.Random(0)
    all_coords = [Square4D(*c) for c in itertools.product(range(8), repeat=4)]
    for sq in rng.sample(all_coords, 50):
        moves = list(king_moves(sq, Color.WHITE, board))
        assert len(moves) == len(KING_NEIGHBORS[sq]), sq


# --- Chebyshev-1 shape ------------------------------------------------------


def test_king_moves_all_chebyshev_1_from_origin() -> None:
    board = Board4D()
    origin = Square4D(3, 3, 3, 3)
    for move in king_moves(origin, Color.WHITE, board):
        assert move.from_sq.chebyshev_distance(move.to_sq) == 1


# --- blockers and captures --------------------------------------------------


def test_king_does_not_land_on_friendly_piece() -> None:
    board = Board4D()
    origin = Square4D(3, 3, 3, 3)
    board.place(origin, _white_king())
    board.place(Square4D(4, 4, 3, 3), _white_rook())
    targets = {move.to_sq for move in king_moves(origin, Color.WHITE, board)}
    assert Square4D(4, 4, 3, 3) not in targets


def test_king_captures_enemy_piece_at_target() -> None:
    board = Board4D()
    origin = Square4D(3, 3, 3, 3)
    board.place(origin, _white_king())
    board.place(Square4D(4, 4, 3, 3), _black_rook())
    targets = {move.to_sq for move in king_moves(origin, Color.WHITE, board)}
    assert Square4D(4, 4, 3, 3) in targets


# --- push/pop integration ---------------------------------------------------


def test_push_and_pop_king_round_trip() -> None:
    board = Board4D()
    origin = Square4D(3, 3, 3, 3)
    target = Square4D(4, 4, 4, 4)
    board.place(origin, _white_king())
    board.push(Move4D(from_sq=origin, to_sq=target))
    assert board.occupant(target) == _white_king()
    board.pop()
    assert board.occupant(origin) == _white_king()
    assert board.occupant(target) is None


def test_push_king_captures_and_pop_restores() -> None:
    board = Board4D()
    origin = Square4D(3, 3, 3, 3)
    target = Square4D(4, 3, 3, 3)
    board.place(origin, _white_king())
    board.place(target, _black_king())
    board.push(Move4D(from_sq=origin, to_sq=target))
    assert board.occupant(target) == _white_king()
    board.pop()
    assert board.occupant(origin) == _white_king()
    assert board.occupant(target) == _black_king()
