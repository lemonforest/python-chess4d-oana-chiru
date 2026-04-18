"""Legality-filter tests (paper §3.4, Definitions 3-5, Remark 1).

Citations refer to Oana & Chiru, *A Mathematical Framework for
Four-Dimensional Chess*, MDPI AppliedMath 6(3):48, 2026
(DOI 10.3390/appliedmath6030048).

These tests exercise :class:`GameState.push`'s king-safety rejection on
hand-built positions. The most important case is **Remark 1**: when a
side has multiple kings, a move is legal only if *every* friendly king
is safe after the move. Saving one king at the cost of exposing
another is illegal.
"""

from __future__ import annotations

import pytest

from chess4d import (
    Board4D,
    Color,
    GameState,
    IllegalMoveError,
    Move4D,
    PieceType,
    Piece,
    Square4D,
)


def _white(pt: PieceType) -> Piece:
    return Piece(Color.WHITE, pt)


def _black(pt: PieceType) -> Piece:
    return Piece(Color.BLACK, pt)


def _snapshot(board: Board4D) -> dict[Square4D, Piece]:
    return {sq: p for sq, p in board.pieces_of(Color.WHITE)} | {
        sq: p for sq, p in board.pieces_of(Color.BLACK)
    }


# --- king cannot move into check -------------------------------------------


def test_king_cannot_move_into_attacked_square() -> None:
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _white(PieceType.KING))
    board.place(Square4D(3, 1, 0, 0), _black(PieceType.ROOK))
    state = GameState(board=board, side_to_move=Color.WHITE)
    # Black rook attacks (1, 1, 0, 0) on its -x ray; king must not move there.
    with pytest.raises(IllegalMoveError):
        state.push(Move4D(Square4D(0, 0, 0, 0), Square4D(1, 1, 0, 0)))


# --- absolute pin ----------------------------------------------------------


def test_absolute_pin_blocks_off_line_move() -> None:
    board = Board4D()
    # King at (0,0,0,0), bishop pinned at (3,3,0,0) by enemy bishop at (7,7,0,0).
    # Enemy bishop's -/- XY-diagonal: (6,6), (5,5), (4,4), (3,3)-blocked, continue stops.
    # Removing the white bishop exposes the king.
    board.place(Square4D(0, 0, 0, 0), _white(PieceType.KING))
    board.place(Square4D(3, 3, 0, 0), _white(PieceType.BISHOP))
    board.place(Square4D(7, 7, 0, 0), _black(PieceType.BISHOP))
    state = GameState(board=board, side_to_move=Color.WHITE)
    # Bishop tries to slide along YZ diagonal off the pin line.
    with pytest.raises(IllegalMoveError):
        state.push(Move4D(Square4D(3, 3, 0, 0), Square4D(3, 4, 1, 0)))


def test_absolute_pin_allows_moves_along_pin_line() -> None:
    """A pinned piece can still move along the pin line (toward or
    away from the pinner), since the king remains shielded."""
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _white(PieceType.KING))
    board.place(Square4D(3, 3, 0, 0), _white(PieceType.BISHOP))
    board.place(Square4D(7, 7, 0, 0), _black(PieceType.BISHOP))
    state = GameState(board=board, side_to_move=Color.WHITE)
    # Bishop moves along the pin (XY +/+ diagonal) to (4,4,0,0) — still blocks.
    state.push(Move4D(Square4D(3, 3, 0, 0), Square4D(4, 4, 0, 0)))
    # Successfully pushed — no exception.


# --- discovered check ------------------------------------------------------


def test_discovered_check_rejects_move_that_unblocks_enemy_ray() -> None:
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _white(PieceType.KING))
    board.place(Square4D(3, 0, 0, 0), _white(PieceType.ROOK))  # blocker
    board.place(Square4D(7, 0, 0, 0), _black(PieceType.ROOK))  # pinner along x
    state = GameState(board=board, side_to_move=Color.WHITE)
    # Moving the white rook off the x-axis unblocks the enemy rook's attack.
    with pytest.raises(IllegalMoveError):
        state.push(Move4D(Square4D(3, 0, 0, 0), Square4D(3, 5, 0, 0)))


# --- check-resolving moves -------------------------------------------------


def test_capturing_the_checker_resolves_check() -> None:
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _white(PieceType.KING))
    board.place(Square4D(0, 5, 0, 0), _black(PieceType.ROOK))  # gives check on -y ray
    board.place(Square4D(5, 5, 0, 0), _white(PieceType.ROOK))  # can capture checker
    state = GameState(board=board, side_to_move=Color.WHITE)
    assert state.in_check()
    state.push(Move4D(Square4D(5, 5, 0, 0), Square4D(0, 5, 0, 0)))
    assert not any_king_attacked_white(state)


def any_king_attacked_white(state: GameState) -> bool:
    # Local helper so the test reads cleanly even though side_to_move
    # flipped to Black after the push.
    from chess4d import any_king_attacked

    return any_king_attacked(Color.WHITE, state.board)


def test_blocking_the_check_resolves_check() -> None:
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _white(PieceType.KING))
    board.place(Square4D(0, 5, 0, 0), _black(PieceType.ROOK))  # gives check along -y
    board.place(Square4D(5, 2, 0, 0), _white(PieceType.ROOK))  # can block at (0,2,0,0)
    state = GameState(board=board, side_to_move=Color.WHITE)
    assert state.in_check()
    state.push(Move4D(Square4D(5, 2, 0, 0), Square4D(0, 2, 0, 0)))
    assert not any_king_attacked_white(state)


# --- multi-king Remark 1 ---------------------------------------------------


def test_remark_1_move_that_exposes_second_king_is_illegal() -> None:
    """Two friendly kings both attacked; a move that rescues one while
    leaving the other attacked must be rejected (§3.4 Remark 1)."""
    board = Board4D()
    # Black bishop at (2,2,0,0) attacks two white kings via both XY diagonals.
    board.place(Square4D(2, 2, 0, 0), _black(PieceType.BISHOP))
    board.place(Square4D(0, 0, 0, 0), _white(PieceType.KING))  # on (-1,-1) ray
    board.place(Square4D(5, 5, 0, 0), _white(PieceType.KING))  # on (+1,+1) ray
    state = GameState(board=board, side_to_move=Color.WHITE)
    assert state.in_check()  # at least one king attacked
    # Move king A out of the bishop's (-1,-1) ray; king B still attacked.
    with pytest.raises(IllegalMoveError):
        state.push(Move4D(Square4D(0, 0, 0, 0), Square4D(0, 1, 0, 0)))


def test_remark_1_single_move_that_defends_both_kings_is_legal() -> None:
    """A move that removes the double-attacker rescues all kings
    simultaneously (§3.4 Remark 1, legal branch)."""
    board = Board4D()
    board.place(Square4D(2, 2, 0, 0), _black(PieceType.BISHOP))
    board.place(Square4D(0, 0, 0, 0), _white(PieceType.KING))
    board.place(Square4D(5, 5, 0, 0), _white(PieceType.KING))
    # A white rook that can capture the bishop on its ray from (2,7,0,0).
    board.place(Square4D(2, 7, 0, 0), _white(PieceType.ROOK))
    state = GameState(board=board, side_to_move=Color.WHITE)
    state.push(Move4D(Square4D(2, 7, 0, 0), Square4D(2, 2, 0, 0)))
    assert not any_king_attacked_white(state)


# --- rollback semantics ----------------------------------------------------


def test_illegal_push_leaves_board_and_side_to_move_unchanged() -> None:
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _white(PieceType.KING))
    board.place(Square4D(3, 0, 0, 0), _white(PieceType.ROOK))
    board.place(Square4D(7, 0, 0, 0), _black(PieceType.ROOK))
    state = GameState(board=board, side_to_move=Color.WHITE)
    before = _snapshot(board)
    before_stm = state.side_to_move
    with pytest.raises(IllegalMoveError):
        # Discovered-check move.
        state.push(Move4D(Square4D(3, 0, 0, 0), Square4D(3, 5, 0, 0)))
    assert _snapshot(board) == before
    assert state.side_to_move == before_stm


def test_wrong_color_push_leaves_state_unchanged() -> None:
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _white(PieceType.ROOK))
    board.place(Square4D(7, 7, 0, 0), _black(PieceType.ROOK))
    state = GameState(board=board, side_to_move=Color.WHITE)
    before = _snapshot(board)
    with pytest.raises(IllegalMoveError):
        # Black piece moves during white's turn.
        state.push(Move4D(Square4D(7, 7, 0, 0), Square4D(7, 0, 0, 0)))
    assert _snapshot(board) == before
    assert state.side_to_move == Color.WHITE


# --- legal_moves filters correctly -----------------------------------------


def test_legal_moves_excludes_moves_that_leave_king_in_check() -> None:
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _white(PieceType.KING))
    board.place(Square4D(3, 3, 0, 0), _white(PieceType.BISHOP))
    board.place(Square4D(7, 7, 0, 0), _black(PieceType.BISHOP))
    state = GameState(board=board, side_to_move=Color.WHITE)
    moves = list(state.legal_moves())
    # The pinned bishop can still move along the pin line; off-pin moves are filtered.
    bishop_moves_emitted = [m for m in moves if m.from_sq == Square4D(3, 3, 0, 0)]
    for m in bishop_moves_emitted:
        # Every emitted bishop move must stay on the +x+y / -x-y diagonal.
        dx = m.to_sq.x - 3
        dy = m.to_sq.y - 3
        dz = m.to_sq.z - 0
        dw = m.to_sq.w - 0
        assert dx == dy
        assert dz == 0
        assert dw == 0


def test_legal_moves_empty_when_no_pieces_of_side() -> None:
    board = Board4D()
    board.place(Square4D(7, 7, 7, 7), _black(PieceType.KING))
    state = GameState(board=board, side_to_move=Color.WHITE)
    assert list(state.legal_moves()) == []
