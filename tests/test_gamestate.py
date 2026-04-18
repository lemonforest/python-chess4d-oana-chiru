"""GameState tests (paper §3.4, Definitions 3-5).

Citations refer to Oana & Chiru, *A Mathematical Framework for
Four-Dimensional Chess*, MDPI AppliedMath 6(3):48, 2026
(DOI 10.3390/appliedmath6030048).

Covers side-to-move enforcement, push/pop round-trips, and the
check/checkmate/stalemate predicates on hand-built positions.
"""

from __future__ import annotations

import pytest

from chess4d import (
    Board4D,
    Color,
    GameState,
    IllegalMoveError,
    Move4D,
    PawnAxis,
    Piece,
    PieceType,
    Square4D,
)


def _white(pt: PieceType) -> Piece:
    return Piece(Color.WHITE, pt)


def _black(pt: PieceType) -> Piece:
    return Piece(Color.BLACK, pt)


def _pawn(color: Color, axis: PawnAxis) -> Piece:
    return Piece(color, PieceType.PAWN, axis)


def _snapshot(board: Board4D) -> dict[Square4D, Piece]:
    snap: dict[Square4D, Piece] = {}
    for sq, p in board.pieces_of(Color.WHITE):
        snap[sq] = p
    for sq, p in board.pieces_of(Color.BLACK):
        snap[sq] = p
    return snap


# --- side-to-move enforcement ----------------------------------------------


def test_push_rejects_move_by_wrong_color() -> None:
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _white(PieceType.ROOK))
    board.place(Square4D(7, 7, 0, 0), _black(PieceType.ROOK))
    state = GameState(board=board, side_to_move=Color.WHITE)
    with pytest.raises(IllegalMoveError):
        state.push(Move4D(Square4D(7, 7, 0, 0), Square4D(7, 0, 0, 0)))


def test_push_flips_side_to_move_on_legal_move() -> None:
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _white(PieceType.ROOK))
    state = GameState(board=board, side_to_move=Color.WHITE)
    state.push(Move4D(Square4D(0, 0, 0, 0), Square4D(3, 0, 0, 0)))
    assert state.side_to_move == Color.BLACK


def test_push_on_empty_source_raises() -> None:
    board = Board4D()
    state = GameState(board=board, side_to_move=Color.WHITE)
    with pytest.raises(IllegalMoveError):
        state.push(Move4D(Square4D(0, 0, 0, 0), Square4D(3, 0, 0, 0)))


# --- push / pop round-trip -------------------------------------------------


def test_push_pop_restores_board_and_side() -> None:
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _white(PieceType.ROOK))
    state = GameState(board=board, side_to_move=Color.WHITE)
    before = _snapshot(board)
    state.push(Move4D(Square4D(0, 0, 0, 0), Square4D(4, 0, 0, 0)))
    state.pop()
    assert _snapshot(board) == before
    assert state.side_to_move == Color.WHITE


def test_push_pop_with_capture_restores_enemy() -> None:
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _white(PieceType.ROOK))
    board.place(Square4D(3, 0, 0, 0), _black(PieceType.ROOK))
    state = GameState(board=board, side_to_move=Color.WHITE)
    before = _snapshot(board)
    state.push(Move4D(Square4D(0, 0, 0, 0), Square4D(3, 0, 0, 0)))
    state.pop()
    assert _snapshot(board) == before
    assert state.side_to_move == Color.WHITE


# --- in_check --------------------------------------------------------------


def test_in_check_true_when_side_to_move_king_attacked() -> None:
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _white(PieceType.KING))
    board.place(Square4D(0, 5, 0, 0), _black(PieceType.ROOK))
    state = GameState(board=board, side_to_move=Color.WHITE)
    assert state.in_check()


def test_in_check_false_when_side_to_move_king_safe() -> None:
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _white(PieceType.KING))
    board.place(Square4D(7, 7, 7, 7), _black(PieceType.KING))
    state = GameState(board=board, side_to_move=Color.WHITE)
    assert not state.in_check()


def test_in_check_is_per_side_to_move() -> None:
    """If BLACK is to move and a black king is attacked, in_check is True
    from black's perspective even though white is not under threat."""
    board = Board4D()
    board.place(Square4D(7, 7, 7, 7), _black(PieceType.KING))
    board.place(Square4D(0, 7, 7, 7), _white(PieceType.ROOK))  # attacks along x
    state = GameState(board=board, side_to_move=Color.BLACK)
    assert state.in_check()
    # If instead white were to move, in_check should be False.
    state.side_to_move = Color.WHITE
    assert not state.in_check()


# --- checkmate / stalemate -------------------------------------------------


def _mate_position() -> GameState:
    """Return a hand-built checkmate against BLACK.

    - Black king at (0,0,0,0): attacked by adjacent white king at (1,1,1,1).
    - Every Chebyshev-1 escape from (0,0,0,0) is attacked by that white
      king (or lies off-board).
    - A white rook on the w-axis defends the white king so black cannot
      escape by capturing it (black king would then sit on the rook's
      ray and still be in check).

    The position is artificial (two adjacent kings can't arise in real
    play) but it satisfies §3.4 Def 5 cleanly.
    """
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _black(PieceType.KING))
    board.place(Square4D(1, 1, 1, 1), _white(PieceType.KING))
    board.place(Square4D(1, 1, 1, 7), _white(PieceType.ROOK))
    return GameState(board=board, side_to_move=Color.BLACK)


def test_is_checkmate_true_on_hand_built_mate() -> None:
    state = _mate_position()
    assert state.in_check()
    assert not any(state.legal_moves())
    assert state.is_checkmate()
    assert not state.is_stalemate()


def test_is_checkmate_false_when_an_escape_exists() -> None:
    """Remove the defending white rook — black can now capture the
    attacking white king safely (no other attackers), so it's no
    longer mate."""
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _black(PieceType.KING))
    board.place(Square4D(1, 1, 1, 1), _white(PieceType.KING))
    state = GameState(board=board, side_to_move=Color.BLACK)
    assert state.in_check()
    assert any(state.legal_moves())
    assert not state.is_checkmate()


def _stalemate_position() -> GameState:
    """Return a hand-built stalemate against BLACK.

    - Black king at (0,0,0,0).
    - All 15 Chebyshev-1 escape squares are occupied by friendly black
      Y-pawns; each pawn has no legal move (forward off-board or
      blocked; no captures available).
    - No white pieces, so ``in_check`` is False.

    Because every escape is friendly-blocked and no other black piece
    can move, :meth:`GameState.legal_moves` is empty; the position
    satisfies §3.4 Def 5 (stalemate branch).
    """
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _black(PieceType.KING))
    for dx, dy, dz, dw in _escape_deltas():
        board.place(Square4D(dx, dy, dz, dw), _pawn(Color.BLACK, PawnAxis.Y))
    return GameState(board=board, side_to_move=Color.BLACK)


def _escape_deltas() -> list[tuple[int, int, int, int]]:
    deltas: list[tuple[int, int, int, int]] = []
    for dx in (0, 1):
        for dy in (0, 1):
            for dz in (0, 1):
                for dw in (0, 1):
                    if (dx, dy, dz, dw) != (0, 0, 0, 0):
                        deltas.append((dx, dy, dz, dw))
    return deltas


def test_is_stalemate_true_on_hand_built_stalemate() -> None:
    state = _stalemate_position()
    assert not state.in_check()
    assert not any(state.legal_moves())
    assert state.is_stalemate()
    assert not state.is_checkmate()


def test_is_stalemate_false_when_a_move_exists() -> None:
    """Remove one of the wall pawns; the black king has a legal move."""
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _black(PieceType.KING))
    for dx, dy, dz, dw in _escape_deltas():
        if (dx, dy, dz, dw) == (1, 0, 0, 0):
            continue  # leave this escape square empty
        board.place(Square4D(dx, dy, dz, dw), _pawn(Color.BLACK, PawnAxis.Y))
    state = GameState(board=board, side_to_move=Color.BLACK)
    assert not state.in_check()
    assert any(state.legal_moves())
    assert not state.is_stalemate()


# --- legal_moves general shape ---------------------------------------------


def test_legal_moves_preserves_board_after_iteration() -> None:
    """Make-unmake must leave the board bit-identical."""
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _white(PieceType.KING))
    board.place(Square4D(3, 3, 3, 3), _white(PieceType.QUEEN))
    board.place(Square4D(7, 7, 7, 7), _black(PieceType.KING))
    state = GameState(board=board, side_to_move=Color.WHITE)
    before = _snapshot(board)
    # Consume the whole generator.
    _ = list(state.legal_moves())
    assert _snapshot(board) == before
    assert state.side_to_move == Color.WHITE
