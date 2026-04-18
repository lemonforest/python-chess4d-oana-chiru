"""Tests for :func:`chess4d.pieces.rook.rook_moves` (paper §3.5, §3.8).

Citations refer to Oana & Chiru, *A Mathematical Framework for
Four-Dimensional Chess*, MDPI AppliedMath 6(3):48, 2026
(DOI 10.3390/appliedmath6030048).
"""

from __future__ import annotations

from hypothesis import given

from chess4d import BOARD_SIZE, Board4D, Color, PieceType, Piece, Square4D
from chess4d.pieces import rook_moves

from .conftest import all_squares, interior_squares_strategy, squares_strategy


def _coords_differing(a: Square4D, b: Square4D) -> int:
    return sum(int(ai != bi) for ai, bi in zip(a, b))


def _white_rook() -> Piece:
    return Piece(color=Color.WHITE, piece_type=PieceType.ROOK)


def _black_rook() -> Piece:
    return Piece(color=Color.BLACK, piece_type=PieceType.ROOK)


# --- empty-board mobility (Corollary 1) --------------------------------------


def test_rook_moves_empty_board_corner_has_28_moves() -> None:
    """Corollary 1: 28 moves from the corner of an empty board."""
    board = Board4D()
    moves = list(rook_moves(Square4D(0, 0, 0, 0), Color.WHITE, board))
    assert len(moves) == 28


def test_rook_moves_empty_board_every_square_has_28_moves() -> None:
    """Corollary 1: 28 moves uniformly on an empty board."""
    board = Board4D()
    for sq in all_squares():
        moves = list(rook_moves(sq, Color.WHITE, board))
        assert len(moves) == 28, sq


def test_rook_moves_are_axis_aligned() -> None:
    """Every rook move changes exactly one coordinate (Theorem 2)."""
    board = Board4D()
    origin = Square4D(3, 4, 5, 2)
    for move in rook_moves(origin, Color.WHITE, board):
        assert _coords_differing(move.from_sq, move.to_sq) == 1


def test_rook_moves_from_field_matches_origin() -> None:
    board = Board4D()
    origin = Square4D(2, 2, 2, 2)
    for move in rook_moves(origin, Color.WHITE, board):
        assert move.from_sq == origin


# --- Proposition 2(i): parity flip by d mod 2 --------------------------------


def test_rook_move_parity_flips_by_distance_mod_two() -> None:
    """Paper §3.8, Proposition 2(i): rook move flips parity by ``d mod 2``."""
    board = Board4D()
    origin = Square4D(3, 3, 3, 3)
    for move in rook_moves(origin, Color.WHITE, board):
        d = sum(abs(a - b) for a, b in zip(move.from_sq, move.to_sq))
        expected_flip = d % 2
        actual_flip = (move.from_sq.parity() ^ move.to_sq.parity())
        assert actual_flip == expected_flip


# --- blockers and captures ---------------------------------------------------


def test_rook_stops_at_friendly_blocker_without_capture() -> None:
    board = Board4D()
    origin = Square4D(0, 0, 0, 0)
    board.place(origin, _white_rook())
    # Friendly rook two steps along +x.
    board.place(Square4D(2, 0, 0, 0), _white_rook())
    targets = {move.to_sq for move in rook_moves(origin, Color.WHITE, board)}
    # Only the single empty square between origin and blocker is reachable along +x.
    assert Square4D(1, 0, 0, 0) in targets
    assert Square4D(2, 0, 0, 0) not in targets
    assert Square4D(3, 0, 0, 0) not in targets


def test_rook_captures_opposing_blocker_and_stops() -> None:
    board = Board4D()
    origin = Square4D(0, 0, 0, 0)
    board.place(origin, _white_rook())
    board.place(Square4D(2, 0, 0, 0), _black_rook())
    targets = {move.to_sq for move in rook_moves(origin, Color.WHITE, board)}
    assert Square4D(1, 0, 0, 0) in targets
    assert Square4D(2, 0, 0, 0) in targets  # capture is legal
    assert Square4D(3, 0, 0, 0) not in targets  # ray stops at the captured piece


def test_rook_blocked_direction_counts() -> None:
    """Known mobility from a corner with a friendly blocker adjacent on +x."""
    board = Board4D()
    origin = Square4D(0, 0, 0, 0)
    board.place(origin, _white_rook())
    # Friendly blocker immediately at +x removes the entire +x ray (7 squares).
    board.place(Square4D(1, 0, 0, 0), _white_rook())
    moves = list(rook_moves(origin, Color.WHITE, board))
    # Empty-board corner mobility is 28; blocker kills 7 along +x, no capture.
    assert len(moves) == 28 - 7


def test_rook_opposite_blocker_adjacent_still_allows_capture() -> None:
    board = Board4D()
    origin = Square4D(0, 0, 0, 0)
    board.place(origin, _white_rook())
    board.place(Square4D(1, 0, 0, 0), _black_rook())
    moves = list(rook_moves(origin, Color.WHITE, board))
    # +x ray collapses to a single capture; other 21 moves unaffected.
    assert len(moves) == 28 - 7 + 1


# --- boundary behavior -------------------------------------------------------


def test_rook_from_corner_has_zero_length_rays_on_negative_axes() -> None:
    """From ``(0, 0, 0, 0)`` the four negative-axis rays have length 0."""
    board = Board4D()
    moves = list(rook_moves(Square4D(0, 0, 0, 0), Color.WHITE, board))
    # Only +x, +y, +z, +w rays yield anything; each has 7 targets.
    assert len(moves) == 4 * (BOARD_SIZE - 1)
    for move in moves:
        assert move.to_sq.x >= 0 and move.to_sq.y >= 0 \
            and move.to_sq.z >= 0 and move.to_sq.w >= 0


def test_rook_far_corner_symmetric() -> None:
    """From ``(7, 7, 7, 7)`` the four positive-axis rays have length 0."""
    board = Board4D()
    moves = list(rook_moves(Square4D(7, 7, 7, 7), Color.WHITE, board))
    assert len(moves) == 4 * (BOARD_SIZE - 1)


# --- hypothesis property -----------------------------------------------------


@given(origin=squares_strategy)
def test_rook_empty_board_mobility_28_property(origin: Square4D) -> None:
    """Property: empty-board rook mobility is 28 from every square."""
    board = Board4D()
    moves = list(rook_moves(origin, Color.WHITE, board))
    assert len(moves) == 28


@given(origin=interior_squares_strategy)
def test_rook_moves_always_axis_aligned_property(origin: Square4D) -> None:
    """Property: every generated move changes exactly one coordinate."""
    board = Board4D()
    for move in rook_moves(origin, Color.WHITE, board):
        assert _coords_differing(move.from_sq, move.to_sq) == 1
