"""Halfmove-clock / 50-move-rule tests.

Citations refer to Oana & Chiru, *A Mathematical Framework for
Four-Dimensional Chess*, MDPI AppliedMath 6(3):48, 2026
(DOI 10.3390/appliedmath6030048). The paper inherits FIDE's halfmove-
clock semantics by reference.

The clock increments on every ply; it resets to zero on any pawn move
(push, two-step, capture, en passant, promotion) and on any capture
(regardless of mover). :meth:`GameState.is_fifty_move_draw` is a
claim predicate — True at clock ≥ 100 — not an automatic draw.
"""

from __future__ import annotations

from chess4d import (
    Board4D,
    CastleSide,
    Color,
    GameState,
    Move4D,
    PawnAxis,
    Piece,
    PieceType,
    Square4D,
    initial_position,
)


def _white(pt: PieceType) -> Piece:
    return Piece(Color.WHITE, pt)


def _black(pt: PieceType) -> Piece:
    return Piece(Color.BLACK, pt)


def _pawn(color: Color, axis: PawnAxis) -> Piece:
    return Piece(color, PieceType.PAWN, axis)


def _king(color: Color) -> Piece:
    return Piece(color, PieceType.KING)


def _kings_only(side: Color = Color.WHITE) -> GameState:
    board = Board4D()
    board.place(Square4D(0, 0, 7, 7), _king(Color.WHITE))
    board.place(Square4D(7, 7, 7, 7), _king(Color.BLACK))
    return GameState(board=board, side_to_move=side)


# --- initial state ---------------------------------------------------------


def test_initial_halfmove_clock_is_zero() -> None:
    assert initial_position().halfmove_clock == 0


def test_handbuilt_default_halfmove_clock_is_zero() -> None:
    assert _kings_only().halfmove_clock == 0


# --- clock increments ------------------------------------------------------


def test_non_pawn_non_capture_move_increments_clock() -> None:
    state = _kings_only()
    state.board.place(Square4D(0, 0, 0, 0), _white(PieceType.ROOK))
    state.push(Move4D(Square4D(0, 0, 0, 0), Square4D(5, 0, 0, 0)))
    assert state.halfmove_clock == 1


def test_repeated_non_resetting_moves_keep_accumulating() -> None:
    state = _kings_only()
    state.board.place(Square4D(0, 0, 0, 0), _white(PieceType.ROOK))
    state.board.place(Square4D(0, 1, 0, 0), _black(PieceType.ROOK))
    state.push(Move4D(Square4D(0, 0, 0, 0), Square4D(5, 0, 0, 0)))  # white
    state.push(Move4D(Square4D(0, 1, 0, 0), Square4D(5, 1, 0, 0)))  # black
    state.push(Move4D(Square4D(5, 0, 0, 0), Square4D(0, 0, 0, 0)))  # white
    state.push(Move4D(Square4D(5, 1, 0, 0), Square4D(0, 1, 0, 0)))  # black
    assert state.halfmove_clock == 4


# --- clock resets ----------------------------------------------------------


def test_pawn_move_resets_clock() -> None:
    state = _kings_only()
    state.board.place(Square4D(0, 0, 0, 0), _white(PieceType.ROOK))
    state.board.place(Square4D(3, 1, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    state.board.place(Square4D(0, 5, 0, 0), _black(PieceType.ROOK))
    state.push(Move4D(Square4D(0, 0, 0, 0), Square4D(5, 0, 0, 0)))  # non-reset
    state.push(Move4D(Square4D(0, 5, 0, 0), Square4D(5, 5, 0, 0)))  # non-reset
    assert state.halfmove_clock == 2
    state.push(Move4D(Square4D(3, 1, 0, 0), Square4D(3, 2, 0, 0)))  # pawn one-step
    assert state.halfmove_clock == 0


def test_non_pawn_capture_resets_clock() -> None:
    state = _kings_only()
    state.board.place(Square4D(0, 0, 0, 0), _white(PieceType.ROOK))
    state.board.place(Square4D(5, 0, 0, 0), _black(PieceType.ROOK))
    # Push a few filler moves first to build a non-zero clock… actually
    # on a fresh state the clock is 0, so direct capture is enough.
    state.push(Move4D(Square4D(0, 0, 0, 0), Square4D(5, 0, 0, 0)))
    assert state.halfmove_clock == 0  # reset by capture


def test_en_passant_capture_resets_clock() -> None:
    state = _kings_only(Color.WHITE)
    state.board.place(Square4D(3, 4, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    state.board.place(Square4D(4, 6, 0, 0), _pawn(Color.BLACK, PawnAxis.Y))
    state.side_to_move = Color.BLACK
    state.push(Move4D(Square4D(4, 6, 0, 0), Square4D(4, 4, 0, 0)))  # two-step (reset)
    assert state.halfmove_clock == 0
    state.push(
        Move4D(Square4D(3, 4, 0, 0), Square4D(4, 5, 0, 0), is_en_passant=True)
    )
    assert state.halfmove_clock == 0


def test_castling_does_not_reset_clock() -> None:
    """Castling is neither a pawn move nor a capture — clock ticks."""
    board = Board4D()
    board.place(Square4D(4, 0, 0, 0), _white(PieceType.KING))
    board.place(Square4D(7, 0, 0, 0), _white(PieceType.ROOK))
    board.place(Square4D(0, 0, 7, 7), _king(Color.BLACK))
    state = GameState(
        board=board,
        side_to_move=Color.WHITE,
        castling_rights=frozenset({(Color.WHITE, 0, 0, CastleSide.KINGSIDE)}),
        halfmove_clock=5,  # pretend we're mid-game
    )
    state.push(
        Move4D(Square4D(4, 0, 0, 0), Square4D(6, 0, 0, 0), is_castling=True)
    )
    assert state.halfmove_clock == 6


# --- undo restores clock ---------------------------------------------------


def test_pop_restores_clock_after_non_resetting_move() -> None:
    state = _kings_only()
    state.board.place(Square4D(0, 0, 0, 0), _white(PieceType.ROOK))
    state.push(Move4D(Square4D(0, 0, 0, 0), Square4D(5, 0, 0, 0)))
    assert state.halfmove_clock == 1
    state.pop()
    assert state.halfmove_clock == 0


def test_pop_restores_clock_after_pawn_move_reset() -> None:
    state = _kings_only()
    state.board.place(Square4D(3, 1, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    state.halfmove_clock = 42  # mid-game
    state.push(Move4D(Square4D(3, 1, 0, 0), Square4D(3, 2, 0, 0)))
    assert state.halfmove_clock == 0
    state.pop()
    assert state.halfmove_clock == 42


def test_pop_restores_clock_after_capture_reset() -> None:
    state = _kings_only()
    state.board.place(Square4D(0, 0, 0, 0), _white(PieceType.ROOK))
    state.board.place(Square4D(5, 0, 0, 0), _black(PieceType.ROOK))
    state.halfmove_clock = 17
    state.push(Move4D(Square4D(0, 0, 0, 0), Square4D(5, 0, 0, 0)))
    assert state.halfmove_clock == 0
    state.pop()
    assert state.halfmove_clock == 17


# --- is_fifty_move_draw predicate ------------------------------------------


def test_is_fifty_move_draw_false_below_threshold() -> None:
    state = _kings_only()
    state.halfmove_clock = 99
    assert not state.is_fifty_move_draw()


def test_is_fifty_move_draw_true_at_100() -> None:
    state = _kings_only()
    state.halfmove_clock = 100
    assert state.is_fifty_move_draw()


def test_is_fifty_move_draw_true_above_100() -> None:
    state = _kings_only()
    state.halfmove_clock = 250
    assert state.is_fifty_move_draw()


def test_is_fifty_move_draw_false_at_initial_position() -> None:
    assert not initial_position().is_fifty_move_draw()
