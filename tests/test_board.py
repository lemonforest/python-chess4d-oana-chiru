"""Tests for :class:`Board4D` construction and piece-list primitives.

Citations refer to Oana & Chiru, *A Mathematical Framework for
Four-Dimensional Chess*, MDPI AppliedMath 6(3):48, 2026
(DOI 10.3390/appliedmath6030048).
"""

from __future__ import annotations

import pytest

from chess4d import Board4D, Color, PieceType, Piece, Square4D


def _white_rook() -> Piece:
    return Piece(color=Color.WHITE, piece_type=PieceType.ROOK)


def _black_rook() -> Piece:
    return Piece(color=Color.BLACK, piece_type=PieceType.ROOK)


# --- construction + occupant lookup -----------------------------------------


def test_board4d_constructs_empty_and_occupant_returns_none() -> None:
    """Fresh board has no pieces; ``occupant`` returns ``None`` everywhere."""
    board = Board4D()
    assert board.occupant(Square4D(0, 0, 0, 0)) is None


def test_board4d_empty_on_arbitrary_square() -> None:
    board = Board4D()
    assert board.occupant(Square4D(3, 4, 5, 6)) is None


# --- place + remove ----------------------------------------------------------


def test_board_place_and_occupant_roundtrip() -> None:
    board = Board4D()
    sq = Square4D(2, 2, 2, 2)
    rook = _white_rook()
    board.place(sq, rook)
    assert board.occupant(sq) == rook


def test_board_place_on_occupied_square_raises() -> None:
    """Placing onto an already-occupied square is a programming error."""
    board = Board4D()
    sq = Square4D(1, 1, 1, 1)
    board.place(sq, _white_rook())
    with pytest.raises(ValueError):
        board.place(sq, _black_rook())


def test_board_remove_clears_occupant() -> None:
    board = Board4D()
    sq = Square4D(0, 0, 0, 0)
    board.place(sq, _white_rook())
    board.remove(sq)
    assert board.occupant(sq) is None


def test_board_remove_empty_square_raises() -> None:
    board = Board4D()
    with pytest.raises(KeyError):
        board.remove(Square4D(7, 7, 7, 7))


# --- equality ----------------------------------------------------------------


def test_two_empty_boards_are_equal() -> None:
    assert Board4D() == Board4D()


def test_boards_with_same_pieces_are_equal() -> None:
    a = Board4D()
    b = Board4D()
    sq = Square4D(4, 4, 4, 4)
    a.place(sq, _white_rook())
    b.place(sq, _white_rook())
    assert a == b


def test_boards_with_different_pieces_are_not_equal() -> None:
    a = Board4D()
    b = Board4D()
    sq = Square4D(4, 4, 4, 4)
    a.place(sq, _white_rook())
    b.place(sq, _black_rook())
    assert a != b


# --- pieces_of ---------------------------------------------------------------


def test_pieces_of_empty_board_yields_nothing() -> None:
    board = Board4D()
    assert list(board.pieces_of(Color.WHITE)) == []
    assert list(board.pieces_of(Color.BLACK)) == []


def test_pieces_of_filters_by_color() -> None:
    board = Board4D()
    white_sq = Square4D(0, 0, 0, 0)
    black_sq = Square4D(7, 7, 7, 7)
    white_rook = _white_rook()
    black_rook = _black_rook()
    board.place(white_sq, white_rook)
    board.place(black_sq, black_rook)
    white_pairs = list(board.pieces_of(Color.WHITE))
    black_pairs = list(board.pieces_of(Color.BLACK))
    assert white_pairs == [(white_sq, white_rook)]
    assert black_pairs == [(black_sq, black_rook)]


def test_pieces_of_returns_all_matching_color() -> None:
    board = Board4D()
    squares = [Square4D(0, 0, 0, 0), Square4D(1, 1, 1, 1), Square4D(2, 2, 2, 2)]
    for sq in squares:
        board.place(sq, _white_rook())
    board.place(Square4D(7, 7, 7, 7), _black_rook())
    white_squares = {sq for sq, _ in board.pieces_of(Color.WHITE)}
    assert white_squares == set(squares)


def test_pieces_of_mixed_types_filters_only_by_color() -> None:
    """``pieces_of`` returns pieces regardless of type, filtering only by color."""
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), Piece(Color.WHITE, PieceType.ROOK))
    board.place(Square4D(1, 0, 0, 0), Piece(Color.WHITE, PieceType.KING))
    board.place(Square4D(2, 0, 0, 0), Piece(Color.WHITE, PieceType.QUEEN))
    piece_types = {p.piece_type for _, p in board.pieces_of(Color.WHITE)}
    assert piece_types == {PieceType.ROOK, PieceType.KING, PieceType.QUEEN}
