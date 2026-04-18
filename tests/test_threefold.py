"""Threefold-repetition tests (paper §4.7).

:meth:`GameState.is_threefold_repetition` is a FIDE-style claim
predicate — ``True`` iff the current position hash has occurred at
least three times in :attr:`GameState.position_history`. Positions are
compared by placement, side-to-move, castling rights, and en-passant
target; halfmove clock is excluded.
"""

from __future__ import annotations

from chess4d import (
    Board4D,
    Color,
    GameState,
    Move4D,
    Piece,
    PieceType,
    Square4D,
    initial_position,
)


def _king(color: Color) -> Piece:
    return Piece(color, PieceType.KING)


def _white(pt: PieceType) -> Piece:
    return Piece(Color.WHITE, pt)


def _black(pt: PieceType) -> Piece:
    return Piece(Color.BLACK, pt)


def _two_kings_on_rails() -> GameState:
    """Two kings on a board with room to shuffle back and forth."""
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _king(Color.WHITE))
    board.place(Square4D(7, 7, 0, 0), _king(Color.BLACK))
    return GameState(board=board, side_to_move=Color.WHITE)


# --- predicate bounds -----------------------------------------------------


def test_initial_position_is_not_threefold() -> None:
    assert not initial_position().is_threefold_repetition()


def test_fresh_kings_only_is_not_threefold() -> None:
    assert not _two_kings_on_rails().is_threefold_repetition()


# --- occurrence counting --------------------------------------------------


def test_position_seen_once_is_not_threefold() -> None:
    state = _two_kings_on_rails()
    # After one ply the current position has appeared once.
    state.push(Move4D(Square4D(0, 0, 0, 0), Square4D(1, 0, 0, 0)))
    assert not state.is_threefold_repetition()


def test_position_seen_twice_is_not_threefold() -> None:
    """Four plies return to the starting position (2 occurrences)."""
    state = _two_kings_on_rails()
    state.push(Move4D(Square4D(0, 0, 0, 0), Square4D(1, 0, 0, 0)))  # W out
    state.push(Move4D(Square4D(7, 7, 0, 0), Square4D(6, 7, 0, 0)))  # B out
    state.push(Move4D(Square4D(1, 0, 0, 0), Square4D(0, 0, 0, 0)))  # W back
    state.push(Move4D(Square4D(6, 7, 0, 0), Square4D(7, 7, 0, 0)))  # B back
    # Now state hash equals the initial hash; it has occurred twice total.
    assert not state.is_threefold_repetition()


def test_position_seen_three_times_triggers() -> None:
    """Eight plies (two full cycles) produce 3 occurrences of the starting position."""
    state = _two_kings_on_rails()
    for _ in range(2):
        state.push(Move4D(Square4D(0, 0, 0, 0), Square4D(1, 0, 0, 0)))
        state.push(Move4D(Square4D(7, 7, 0, 0), Square4D(6, 7, 0, 0)))
        state.push(Move4D(Square4D(1, 0, 0, 0), Square4D(0, 0, 0, 0)))
        state.push(Move4D(Square4D(6, 7, 0, 0), Square4D(7, 7, 0, 0)))
    assert state.is_threefold_repetition()


def test_leaving_the_repeated_position_clears_the_claim() -> None:
    """After reaching threefold, one more ply into a fresh position clears it."""
    state = _two_kings_on_rails()
    for _ in range(2):
        state.push(Move4D(Square4D(0, 0, 0, 0), Square4D(1, 0, 0, 0)))
        state.push(Move4D(Square4D(7, 7, 0, 0), Square4D(6, 7, 0, 0)))
        state.push(Move4D(Square4D(1, 0, 0, 0), Square4D(0, 0, 0, 0)))
        state.push(Move4D(Square4D(6, 7, 0, 0), Square4D(7, 7, 0, 0)))
    assert state.is_threefold_repetition()
    # Step into a position that wasn't part of the shuffle — the cycle
    # only visited squares (0,0), (1,0) for white; (0,1) is fresh.
    state.push(Move4D(Square4D(0, 0, 0, 0), Square4D(0, 1, 0, 0)))
    assert not state.is_threefold_repetition()


# --- pop restores pre-threefold state -------------------------------------


def test_pop_can_unwind_past_threefold() -> None:
    state = _two_kings_on_rails()
    for _ in range(2):
        state.push(Move4D(Square4D(0, 0, 0, 0), Square4D(1, 0, 0, 0)))
        state.push(Move4D(Square4D(7, 7, 0, 0), Square4D(6, 7, 0, 0)))
        state.push(Move4D(Square4D(1, 0, 0, 0), Square4D(0, 0, 0, 0)))
        state.push(Move4D(Square4D(6, 7, 0, 0), Square4D(7, 7, 0, 0)))
    assert state.is_threefold_repetition()
    state.pop()  # undo last black-king-returns ply
    # Now the starting position has only occurred twice in history.
    assert not state.is_threefold_repetition()
