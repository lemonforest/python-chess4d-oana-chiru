"""Castling tests (paper §3.9 Def 10).

Citations refer to Oana & Chiru, *A Mathematical Framework for
Four-Dimensional Chess*, MDPI AppliedMath 6(3):48, 2026
(DOI 10.3390/appliedmath6030048).

Castling in 4D is restricted to the X-axis within a single ``(z, w)``
-slice, but its *attack constraint is global*: every square the king
traverses must be unattacked from any ``(z', w')`` slice. Rights-
tracking follows standard chess, extended to 112 independent rights
at the Oana-Chiru starting position (4+24 slices × 2 colors × 2 sides).
"""

from __future__ import annotations

import pytest

from chess4d import (
    BOARD_SIZE,
    Board4D,
    CastleSide,
    Color,
    GameState,
    IllegalMoveError,
    Move4D,
    Piece,
    PieceType,
    Square4D,
    initial_position,
)


def _white(pt: PieceType) -> Piece:
    return Piece(Color.WHITE, pt)


def _black(pt: PieceType) -> Piece:
    return Piece(Color.BLACK, pt)


def _snapshot(board: Board4D) -> dict[Square4D, Piece]:
    return {sq: p for sq, p in board.pieces_of(Color.WHITE)} | {
        sq: p for sq, p in board.pieces_of(Color.BLACK)
    }


def _castling_ready_position(
    color: Color = Color.WHITE,
    z: int = 0,
    w: int = 0,
    side: CastleSide = CastleSide.KINGSIDE,
) -> GameState:
    """Return a minimal position where ``color`` can castle on ``(z, w, side)``.

    Only the relevant king and rook are placed; the opposing king is
    tucked away at (0, 0, 7, 7) so the position is well-formed (both
    sides present) without interfering.
    """
    board = Board4D()
    back_y = 0 if color is Color.WHITE else BOARD_SIZE - 1
    board.place(Square4D(4, back_y, z, w), Piece(color, PieceType.KING))
    rook_x = BOARD_SIZE - 1 if side is CastleSide.KINGSIDE else 0
    board.place(Square4D(rook_x, back_y, z, w), Piece(color, PieceType.ROOK))
    # Opposing king far away so in_check and any_king_attacked are well-defined.
    other = Color(1 - color)
    board.place(Square4D(0, 0, 7, 7), Piece(other, PieceType.KING))
    rights = frozenset({(color, z, w, side)})
    return GameState(board=board, side_to_move=color, castling_rights=rights)


# --- initial castling rights -----------------------------------------------


def test_initial_castling_rights_cardinality() -> None:
    """Paper §3.3 partition × §3.9 Def 10: 28 populated slices per color
    × 2 sides = 56 rights per color, 112 total."""
    gs = initial_position()
    white = [r for r in gs.castling_rights if r[0] is Color.WHITE]
    black = [r for r in gs.castling_rights if r[0] is Color.BLACK]
    assert len(white) == 56
    assert len(black) == 56
    assert len(gs.castling_rights) == 112


def test_initial_castling_rights_has_entry_per_populated_slice_per_side() -> None:
    gs = initial_position()
    # Central slice (3, 3) has both colors, both sides.
    assert (Color.WHITE, 3, 3, CastleSide.KINGSIDE) in gs.castling_rights
    assert (Color.WHITE, 3, 3, CastleSide.QUEENSIDE) in gs.castling_rights
    assert (Color.BLACK, 3, 3, CastleSide.KINGSIDE) in gs.castling_rights
    assert (Color.BLACK, 3, 3, CastleSide.QUEENSIDE) in gs.castling_rights
    # White-only slice: no black rights there.
    assert (Color.WHITE, 0, 0, CastleSide.KINGSIDE) in gs.castling_rights
    assert (Color.BLACK, 0, 0, CastleSide.KINGSIDE) not in gs.castling_rights
    # Black-only slice: no white rights there.
    assert (Color.BLACK, 0, 4, CastleSide.KINGSIDE) in gs.castling_rights
    assert (Color.WHITE, 0, 4, CastleSide.KINGSIDE) not in gs.castling_rights
    # Empty slice has no rights for either color.
    assert (Color.WHITE, 3, 0, CastleSide.KINGSIDE) not in gs.castling_rights
    assert (Color.BLACK, 3, 0, CastleSide.KINGSIDE) not in gs.castling_rights


# --- rights revocation -----------------------------------------------------


def test_moving_a_king_revokes_both_sides_on_its_slice() -> None:
    state = _castling_ready_position()
    # Give the same slice the queenside rook too so both rights are initially present.
    state.board.place(Square4D(0, 0, 0, 0), _white(PieceType.ROOK))
    state.castling_rights = state.castling_rights | {
        (Color.WHITE, 0, 0, CastleSide.QUEENSIDE)
    }
    assert (Color.WHITE, 0, 0, CastleSide.KINGSIDE) in state.castling_rights
    assert (Color.WHITE, 0, 0, CastleSide.QUEENSIDE) in state.castling_rights
    # Normal non-castling king move (x=4 → x=4, y=1).
    state.push(Move4D(Square4D(4, 0, 0, 0), Square4D(4, 1, 0, 0)))
    assert (Color.WHITE, 0, 0, CastleSide.KINGSIDE) not in state.castling_rights
    assert (Color.WHITE, 0, 0, CastleSide.QUEENSIDE) not in state.castling_rights


def test_moving_a_kingside_rook_revokes_only_that_right() -> None:
    state = _castling_ready_position(side=CastleSide.KINGSIDE)
    state.board.place(Square4D(0, 0, 0, 0), _white(PieceType.ROOK))
    state.castling_rights = state.castling_rights | {
        (Color.WHITE, 0, 0, CastleSide.QUEENSIDE)
    }
    state.push(Move4D(Square4D(7, 0, 0, 0), Square4D(7, 4, 0, 0)))
    assert (Color.WHITE, 0, 0, CastleSide.KINGSIDE) not in state.castling_rights
    assert (Color.WHITE, 0, 0, CastleSide.QUEENSIDE) in state.castling_rights


def test_capturing_a_rook_on_its_home_square_revokes_opponent_right() -> None:
    board = Board4D()
    board.place(Square4D(4, 0, 0, 0), _white(PieceType.KING))
    # White rook on the black rook's kingside home corner — we'll have it capture.
    board.place(Square4D(7, 1, 0, 0), _white(PieceType.ROOK))
    board.place(Square4D(7, 7, 0, 0), _black(PieceType.ROOK))  # black's home corner
    board.place(Square4D(4, 7, 0, 0), _black(PieceType.KING))
    rights = frozenset({
        (Color.BLACK, 0, 0, CastleSide.KINGSIDE),
        (Color.BLACK, 0, 0, CastleSide.QUEENSIDE),
    })
    state = GameState(
        board=board, side_to_move=Color.WHITE, castling_rights=rights
    )
    # White rook captures black rook on black's kingside corner.
    state.push(Move4D(Square4D(7, 1, 0, 0), Square4D(7, 7, 0, 0)))
    assert (Color.BLACK, 0, 0, CastleSide.KINGSIDE) not in state.castling_rights
    assert (Color.BLACK, 0, 0, CastleSide.QUEENSIDE) in state.castling_rights


def test_non_rook_capture_on_a_home_corner_does_not_revoke() -> None:
    """A capture on a back-rank corner only revokes rights if the
    captured piece was a rook."""
    board = Board4D()
    board.place(Square4D(4, 0, 0, 0), _white(PieceType.KING))
    board.place(Square4D(7, 1, 0, 0), _white(PieceType.ROOK))
    # Black bishop parked on what would be a rook's home corner.
    board.place(Square4D(7, 7, 0, 0), _black(PieceType.BISHOP))
    board.place(Square4D(4, 7, 0, 0), _black(PieceType.KING))
    rights = frozenset({
        (Color.BLACK, 0, 0, CastleSide.KINGSIDE),
        (Color.BLACK, 0, 0, CastleSide.QUEENSIDE),
    })
    state = GameState(
        board=board, side_to_move=Color.WHITE, castling_rights=rights
    )
    state.push(Move4D(Square4D(7, 1, 0, 0), Square4D(7, 7, 0, 0)))
    # Bishop captured, but it wasn't a rook — rights untouched.
    assert (Color.BLACK, 0, 0, CastleSide.KINGSIDE) in state.castling_rights
    assert (Color.BLACK, 0, 0, CastleSide.QUEENSIDE) in state.castling_rights


# --- legal castling --------------------------------------------------------


def test_kingside_castling_moves_king_and_rook_to_correct_squares() -> None:
    state = _castling_ready_position(side=CastleSide.KINGSIDE)
    state.push(Move4D(Square4D(4, 0, 0, 0), Square4D(6, 0, 0, 0), is_castling=True))
    # King at (6, 0, 0, 0), rook at (5, 0, 0, 0).
    king = state.board.occupant(Square4D(6, 0, 0, 0))
    rook = state.board.occupant(Square4D(5, 0, 0, 0))
    assert king is not None and king.piece_type is PieceType.KING
    assert rook is not None and rook.piece_type is PieceType.ROOK
    assert state.board.occupant(Square4D(4, 0, 0, 0)) is None
    assert state.board.occupant(Square4D(7, 0, 0, 0)) is None


def test_queenside_castling_moves_king_and_rook_to_correct_squares() -> None:
    state = _castling_ready_position(side=CastleSide.QUEENSIDE)
    state.push(Move4D(Square4D(4, 0, 0, 0), Square4D(2, 0, 0, 0), is_castling=True))
    king = state.board.occupant(Square4D(2, 0, 0, 0))
    rook = state.board.occupant(Square4D(3, 0, 0, 0))
    assert king is not None and king.piece_type is PieceType.KING
    assert rook is not None and rook.piece_type is PieceType.ROOK
    assert state.board.occupant(Square4D(4, 0, 0, 0)) is None
    assert state.board.occupant(Square4D(0, 0, 0, 0)) is None


def test_castling_revokes_both_rights_on_that_slice() -> None:
    state = _castling_ready_position(side=CastleSide.KINGSIDE)
    # Add queenside rights + rook; castling kingside should revoke both.
    state.board.place(Square4D(0, 0, 0, 0), _white(PieceType.ROOK))
    state.castling_rights = state.castling_rights | {
        (Color.WHITE, 0, 0, CastleSide.QUEENSIDE)
    }
    state.push(Move4D(Square4D(4, 0, 0, 0), Square4D(6, 0, 0, 0), is_castling=True))
    assert (Color.WHITE, 0, 0, CastleSide.KINGSIDE) not in state.castling_rights
    assert (Color.WHITE, 0, 0, CastleSide.QUEENSIDE) not in state.castling_rights


def test_black_can_castle_on_its_own_back_rank() -> None:
    state = _castling_ready_position(color=Color.BLACK, side=CastleSide.KINGSIDE)
    state.push(
        Move4D(
            Square4D(4, BOARD_SIZE - 1, 0, 0),
            Square4D(6, BOARD_SIZE - 1, 0, 0),
            is_castling=True,
        )
    )
    king = state.board.occupant(Square4D(6, BOARD_SIZE - 1, 0, 0))
    rook = state.board.occupant(Square4D(5, BOARD_SIZE - 1, 0, 0))
    assert king is not None and king.color is Color.BLACK
    assert rook is not None and rook.color is Color.BLACK


# --- illegal castling ------------------------------------------------------


def test_castling_without_right_is_rejected() -> None:
    state = _castling_ready_position(side=CastleSide.KINGSIDE)
    state.castling_rights = frozenset()  # rights revoked manually
    with pytest.raises(IllegalMoveError):
        state.push(
            Move4D(Square4D(4, 0, 0, 0), Square4D(6, 0, 0, 0), is_castling=True)
        )


def test_castling_blocked_by_piece_between_king_and_rook() -> None:
    state = _castling_ready_position(side=CastleSide.KINGSIDE)
    state.board.place(Square4D(5, 0, 0, 0), _white(PieceType.BISHOP))  # blocker
    with pytest.raises(IllegalMoveError):
        state.push(
            Move4D(Square4D(4, 0, 0, 0), Square4D(6, 0, 0, 0), is_castling=True)
        )


def test_castling_out_of_check_is_rejected() -> None:
    state = _castling_ready_position(side=CastleSide.KINGSIDE)
    # Black rook at (4, 5, 0, 0) attacks the white king along -y.
    # Replace the far-away black king with one that doesn't interfere here,
    # then add an attacker. Use an enemy rook; it puts white king in check.
    state.board.place(Square4D(4, 5, 0, 0), _black(PieceType.ROOK))
    assert state.in_check()
    with pytest.raises(IllegalMoveError):
        state.push(
            Move4D(Square4D(4, 0, 0, 0), Square4D(6, 0, 0, 0), is_castling=True)
        )


def test_castling_through_attacked_intermediate_square_is_rejected() -> None:
    state = _castling_ready_position(side=CastleSide.KINGSIDE)
    # Enemy rook attacking (5, 0, 0, 0) — the middle transit square —
    # from a DIFFERENT slice (§3.9 Def 10 "global attack" clause).
    state.board.place(Square4D(5, 0, 0, 1), _black(PieceType.ROOK))
    assert not state.in_check()  # king itself not currently attacked
    with pytest.raises(IllegalMoveError):
        state.push(
            Move4D(Square4D(4, 0, 0, 0), Square4D(6, 0, 0, 0), is_castling=True)
        )


def test_castling_into_attacked_destination_is_rejected() -> None:
    state = _castling_ready_position(side=CastleSide.KINGSIDE)
    # Enemy rook attacking (6, 0, 0, 0) — the king's destination square —
    # via the w-axis from another slice.
    state.board.place(Square4D(6, 0, 0, 1), _black(PieceType.ROOK))
    with pytest.raises(IllegalMoveError):
        state.push(
            Move4D(Square4D(4, 0, 0, 0), Square4D(6, 0, 0, 0), is_castling=True)
        )


def test_castling_move_with_wrong_delta_is_rejected() -> None:
    state = _castling_ready_position(side=CastleSide.KINGSIDE)
    # is_castling=True but dx = 1 instead of 2.
    with pytest.raises(IllegalMoveError):
        state.push(
            Move4D(Square4D(4, 0, 0, 0), Square4D(5, 0, 0, 0), is_castling=True)
        )


def test_castling_with_non_king_mover_is_rejected() -> None:
    """A non-king at x=4 attempting to castle gets rejected regardless
    of rights and geometry."""
    board = Board4D()
    board.place(Square4D(4, 0, 0, 0), _white(PieceType.BISHOP))  # NOT a king
    board.place(Square4D(7, 0, 0, 0), _white(PieceType.ROOK))
    # Real white king off-slice so any_king_attacked has something to scan.
    board.place(Square4D(0, 0, 7, 7), _white(PieceType.KING))
    board.place(Square4D(0, 7, 7, 7), _black(PieceType.KING))
    rights = frozenset({(Color.WHITE, 0, 0, CastleSide.KINGSIDE)})
    state = GameState(board=board, side_to_move=Color.WHITE, castling_rights=rights)
    with pytest.raises(IllegalMoveError):
        state.push(
            Move4D(Square4D(4, 0, 0, 0), Square4D(6, 0, 0, 0), is_castling=True)
        )


# --- undo ------------------------------------------------------------------


def test_castling_undo_restores_board_and_rights_and_side() -> None:
    state = _castling_ready_position(side=CastleSide.KINGSIDE)
    before_board = _snapshot(state.board)
    before_rights = state.castling_rights
    before_stm = state.side_to_move
    state.push(Move4D(Square4D(4, 0, 0, 0), Square4D(6, 0, 0, 0), is_castling=True))
    state.pop()
    assert _snapshot(state.board) == before_board
    assert state.castling_rights == before_rights
    assert state.side_to_move == before_stm


def test_failed_castling_leaves_state_unchanged() -> None:
    state = _castling_ready_position(side=CastleSide.KINGSIDE)
    state.board.place(Square4D(5, 0, 0, 1), _black(PieceType.ROOK))
    before_board = _snapshot(state.board)
    before_rights = state.castling_rights
    before_stm = state.side_to_move
    with pytest.raises(IllegalMoveError):
        state.push(
            Move4D(Square4D(4, 0, 0, 0), Square4D(6, 0, 0, 0), is_castling=True)
        )
    assert _snapshot(state.board) == before_board
    assert state.castling_rights == before_rights
    assert state.side_to_move == before_stm


# --- legal_moves emission --------------------------------------------------


def test_legal_moves_includes_castling_when_available() -> None:
    state = _castling_ready_position(side=CastleSide.KINGSIDE)
    castles = [m for m in state.legal_moves() if m.is_castling]
    assert len(castles) == 1
    assert castles[0].from_sq == Square4D(4, 0, 0, 0)
    assert castles[0].to_sq == Square4D(6, 0, 0, 0)


def test_legal_moves_omits_castling_when_blocked() -> None:
    state = _castling_ready_position(side=CastleSide.KINGSIDE)
    state.board.place(Square4D(5, 0, 0, 0), _white(PieceType.BISHOP))
    castles = [m for m in state.legal_moves() if m.is_castling]
    assert castles == []
