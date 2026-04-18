"""En-passant tests (paper §3.10 Def 15).

Citations refer to Oana & Chiru, *A Mathematical Framework for
Four-Dimensional Chess*, MDPI AppliedMath 6(3):48, 2026
(DOI 10.3390/appliedmath6030048).

En passant in 4D is defined independently for Y-oriented and W-
oriented pawns. The *axis* restriction (Def 15 final sentence) is
load-bearing: a Y-pawn cannot en-passant capture a W-pawn, even
when the geometry would otherwise align. En-passant state is
transient — it persists for exactly one ply after the enabling
two-step.
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
    initial_position,
)


def _pawn(color: Color, axis: PawnAxis) -> Piece:
    return Piece(color, PieceType.PAWN, axis)


def _king(color: Color) -> Piece:
    return Piece(color, PieceType.KING)


def _snapshot(board: Board4D) -> dict[Square4D, Piece]:
    return {sq: p for sq, p in board.pieces_of(Color.WHITE)} | {
        sq: p for sq, p in board.pieces_of(Color.BLACK)
    }


def _empty_game(side: Color = Color.WHITE) -> GameState:
    """Empty board with both kings safely off-slice — lets us exercise
    ep without tripping king-safety on piece-absence."""
    board = Board4D()
    board.place(Square4D(0, 0, 7, 7), _king(Color.WHITE))
    board.place(Square4D(7, 7, 7, 7), _king(Color.BLACK))
    return GameState(board=board, side_to_move=side)


# --- initial state ---------------------------------------------------------


def test_initial_position_has_no_ep_state() -> None:
    gs = initial_position()
    assert gs.ep_target is None
    assert gs.ep_victim is None
    assert gs.ep_axis is None


# --- two-step sets ep state ------------------------------------------------


def test_white_y_pawn_two_step_sets_ep_state() -> None:
    state = _empty_game(Color.WHITE)
    state.board.place(Square4D(3, 1, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    state.push(Move4D(Square4D(3, 1, 0, 0), Square4D(3, 3, 0, 0)))
    assert state.ep_target == Square4D(3, 2, 0, 0)
    assert state.ep_victim == Square4D(3, 3, 0, 0)
    assert state.ep_axis is PawnAxis.Y


def test_black_y_pawn_two_step_sets_ep_state() -> None:
    state = _empty_game(Color.BLACK)
    state.board.place(Square4D(3, 6, 0, 0), _pawn(Color.BLACK, PawnAxis.Y))
    state.push(Move4D(Square4D(3, 6, 0, 0), Square4D(3, 4, 0, 0)))
    assert state.ep_target == Square4D(3, 5, 0, 0)
    assert state.ep_victim == Square4D(3, 4, 0, 0)
    assert state.ep_axis is PawnAxis.Y


def test_white_w_pawn_two_step_sets_ep_state() -> None:
    state = _empty_game(Color.WHITE)
    state.board.place(Square4D(3, 0, 0, 1), _pawn(Color.WHITE, PawnAxis.W))
    state.push(Move4D(Square4D(3, 0, 0, 1), Square4D(3, 0, 0, 3)))
    assert state.ep_target == Square4D(3, 0, 0, 2)
    assert state.ep_victim == Square4D(3, 0, 0, 3)
    assert state.ep_axis is PawnAxis.W


def test_black_w_pawn_two_step_sets_ep_state() -> None:
    state = _empty_game(Color.BLACK)
    state.board.place(Square4D(3, 0, 0, 6), _pawn(Color.BLACK, PawnAxis.W))
    state.push(Move4D(Square4D(3, 0, 0, 6), Square4D(3, 0, 0, 4)))
    assert state.ep_target == Square4D(3, 0, 0, 5)
    assert state.ep_victim == Square4D(3, 0, 0, 4)
    assert state.ep_axis is PawnAxis.W


# --- ep state clears on next non-two-step move -----------------------------


def test_ep_state_clears_after_single_step_pawn_move() -> None:
    state = _empty_game(Color.WHITE)
    state.board.place(Square4D(3, 1, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    state.board.place(Square4D(5, 6, 0, 0), _pawn(Color.BLACK, PawnAxis.Y))
    state.push(Move4D(Square4D(3, 1, 0, 0), Square4D(3, 3, 0, 0)))  # white two-step
    assert state.ep_target is not None
    state.push(Move4D(Square4D(5, 6, 0, 0), Square4D(5, 5, 0, 0)))  # black one-step
    assert state.ep_target is None
    assert state.ep_victim is None
    assert state.ep_axis is None


def test_ep_state_clears_after_non_pawn_move() -> None:
    state = _empty_game(Color.WHITE)
    state.board.place(Square4D(3, 1, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    state.board.place(Square4D(0, 0, 0, 0), Piece(Color.BLACK, PieceType.ROOK))
    state.push(Move4D(Square4D(3, 1, 0, 0), Square4D(3, 3, 0, 0)))
    state.push(Move4D(Square4D(0, 0, 0, 0), Square4D(0, 4, 0, 0)))  # black rook move
    assert state.ep_target is None


# --- ep capture legal ------------------------------------------------------


def test_en_passant_capture_removes_victim_and_moves_capturer_to_target() -> None:
    state = _empty_game(Color.WHITE)
    # White Y-pawn at (3, 4, 0, 0); black plays a two-step to (4, 4, 0, 0),
    # passing (4, 5, 0, 0). Then white captures en passant.
    state.board.place(Square4D(3, 4, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    state.board.place(Square4D(4, 6, 0, 0), _pawn(Color.BLACK, PawnAxis.Y))
    # Hand the turn to black first so the two-step fires on black's ply.
    state.side_to_move = Color.BLACK
    state.push(Move4D(Square4D(4, 6, 0, 0), Square4D(4, 4, 0, 0)))
    assert state.ep_target == Square4D(4, 5, 0, 0)
    # White captures en passant.
    state.push(
        Move4D(Square4D(3, 4, 0, 0), Square4D(4, 5, 0, 0), is_en_passant=True)
    )
    assert state.board.occupant(Square4D(4, 5, 0, 0)) == _pawn(
        Color.WHITE, PawnAxis.Y
    )
    assert state.board.occupant(Square4D(4, 4, 0, 0)) is None  # victim removed
    assert state.board.occupant(Square4D(3, 4, 0, 0)) is None  # capturer gone


def test_en_passant_capture_clears_ep_state() -> None:
    state = _empty_game(Color.BLACK)
    state.board.place(Square4D(5, 3, 0, 0), _pawn(Color.BLACK, PawnAxis.Y))
    state.board.place(Square4D(4, 1, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    state.side_to_move = Color.WHITE
    state.push(Move4D(Square4D(4, 1, 0, 0), Square4D(4, 3, 0, 0)))  # white two-step
    state.push(
        Move4D(Square4D(5, 3, 0, 0), Square4D(4, 2, 0, 0), is_en_passant=True)
    )
    assert state.ep_target is None
    assert state.ep_victim is None
    assert state.ep_axis is None


# --- ep right expires after one ply ----------------------------------------


def test_ep_unavailable_after_one_ply() -> None:
    state = _empty_game(Color.WHITE)
    state.board.place(Square4D(3, 4, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    state.board.place(Square4D(4, 6, 0, 0), _pawn(Color.BLACK, PawnAxis.Y))
    state.board.place(Square4D(0, 0, 0, 0), Piece(Color.WHITE, PieceType.ROOK))
    state.side_to_move = Color.BLACK
    state.push(Move4D(Square4D(4, 6, 0, 0), Square4D(4, 4, 0, 0)))  # two-step
    # White makes an unrelated move instead of capturing en passant.
    state.push(Move4D(Square4D(0, 0, 0, 0), Square4D(0, 4, 0, 0)))
    assert state.ep_target is None
    # Black now moves something else (anything), and a future attempt
    # by white to ep-capture must be rejected (there's no state).
    state.push(Move4D(Square4D(4, 4, 0, 0), Square4D(4, 3, 0, 0)))  # one-step
    with pytest.raises(IllegalMoveError):
        state.push(
            Move4D(Square4D(3, 4, 0, 0), Square4D(4, 5, 0, 0), is_en_passant=True)
        )


# --- mixed-axis ep is rejected --------------------------------------------


def test_mixed_axis_en_passant_is_rejected() -> None:
    """Y-pawn two-steps; W-pawn on an adjacent x-file tries to capture
    en passant — must be rejected (§3.10 Def 15 final sentence)."""
    state = _empty_game(Color.WHITE)
    state.board.place(Square4D(4, 6, 0, 0), _pawn(Color.BLACK, PawnAxis.Y))
    # W-oriented white pawn sitting at (3, 4, 0, 0) — geometrically next
    # to the Y-pawn's two-step landing, but wrong axis.
    state.board.place(Square4D(3, 4, 0, 0), _pawn(Color.WHITE, PawnAxis.W))
    state.side_to_move = Color.BLACK
    state.push(Move4D(Square4D(4, 6, 0, 0), Square4D(4, 4, 0, 0)))  # Y two-step
    assert state.ep_axis is PawnAxis.Y
    with pytest.raises(IllegalMoveError):
        state.push(
            Move4D(Square4D(3, 4, 0, 0), Square4D(4, 5, 0, 0), is_en_passant=True)
        )


# --- ep candidates in legal_moves -----------------------------------------


def test_legal_moves_includes_en_passant_candidate() -> None:
    state = _empty_game(Color.WHITE)
    state.board.place(Square4D(3, 4, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    state.board.place(Square4D(4, 6, 0, 0), _pawn(Color.BLACK, PawnAxis.Y))
    state.side_to_move = Color.BLACK
    state.push(Move4D(Square4D(4, 6, 0, 0), Square4D(4, 4, 0, 0)))
    ep_moves = [m for m in state.legal_moves() if m.is_en_passant]
    assert len(ep_moves) == 1
    assert ep_moves[0].from_sq == Square4D(3, 4, 0, 0)
    assert ep_moves[0].to_sq == Square4D(4, 5, 0, 0)


def test_legal_moves_omits_en_passant_when_wrong_axis() -> None:
    state = _empty_game(Color.WHITE)
    state.board.place(Square4D(3, 4, 0, 0), _pawn(Color.WHITE, PawnAxis.W))  # wrong axis
    state.board.place(Square4D(4, 6, 0, 0), _pawn(Color.BLACK, PawnAxis.Y))
    state.side_to_move = Color.BLACK
    state.push(Move4D(Square4D(4, 6, 0, 0), Square4D(4, 4, 0, 0)))
    ep_moves = [m for m in state.legal_moves() if m.is_en_passant]
    assert ep_moves == []


# --- slice locality --------------------------------------------------------


def test_en_passant_is_slice_local_not_global() -> None:
    """A two-step on ``(z=0, w=0)`` does not enable ep capture by a pawn
    on ``(z=0, w=1)`` with the same ``(x, y)``. ep is emitted only for
    the specific ep_target square, which is fixed to the two-stepper's
    slice."""
    state = _empty_game(Color.WHITE)
    state.board.place(Square4D(3, 4, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    # Off-slice "tempting" pawn on a different w.
    state.board.place(Square4D(3, 4, 0, 1), _pawn(Color.WHITE, PawnAxis.Y))
    state.board.place(Square4D(4, 6, 0, 0), _pawn(Color.BLACK, PawnAxis.Y))
    state.side_to_move = Color.BLACK
    state.push(Move4D(Square4D(4, 6, 0, 0), Square4D(4, 4, 0, 0)))
    # Only the on-slice white pawn emits an ep candidate.
    ep_moves = [m for m in state.legal_moves() if m.is_en_passant]
    assert len(ep_moves) == 1
    assert ep_moves[0].from_sq == Square4D(3, 4, 0, 0)


# --- undo ------------------------------------------------------------------


def test_en_passant_undo_restores_victim_and_ep_state() -> None:
    state = _empty_game(Color.WHITE)
    state.board.place(Square4D(3, 4, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    state.board.place(Square4D(4, 6, 0, 0), _pawn(Color.BLACK, PawnAxis.Y))
    state.side_to_move = Color.BLACK
    state.push(Move4D(Square4D(4, 6, 0, 0), Square4D(4, 4, 0, 0)))  # two-step
    before_board = _snapshot(state.board)
    before_ep = (state.ep_target, state.ep_victim, state.ep_axis)
    before_stm = state.side_to_move
    state.push(
        Move4D(Square4D(3, 4, 0, 0), Square4D(4, 5, 0, 0), is_en_passant=True)
    )
    state.pop()
    assert _snapshot(state.board) == before_board
    assert (state.ep_target, state.ep_victim, state.ep_axis) == before_ep
    assert state.side_to_move == before_stm


def test_failed_en_passant_leaves_state_unchanged() -> None:
    """An ep attempt without ep state set must reject and leave the
    board + ep fields untouched."""
    state = _empty_game(Color.WHITE)
    state.board.place(Square4D(3, 4, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    state.board.place(Square4D(4, 4, 0, 0), _pawn(Color.BLACK, PawnAxis.Y))
    before_board = _snapshot(state.board)
    with pytest.raises(IllegalMoveError):
        state.push(
            Move4D(Square4D(3, 4, 0, 0), Square4D(4, 5, 0, 0), is_en_passant=True)
        )
    assert _snapshot(state.board) == before_board
    assert state.ep_target is None


# --- ep cannot leave king in check ----------------------------------------


def test_en_passant_leaving_king_in_check_is_rejected() -> None:
    """Ep capture that exposes the capturer's king along a pinning ray
    must be rejected (§3.4 Def 3)."""
    board = Board4D()
    # White king on the y=4 row; a black rook pins along +x behind the
    # white ep-capturer and black victim arrangement.
    board.place(Square4D(0, 4, 0, 0), _king(Color.WHITE))
    board.place(Square4D(3, 4, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))  # capturer
    board.place(Square4D(4, 4, 0, 0), _pawn(Color.BLACK, PawnAxis.Y))  # victim
    board.place(Square4D(7, 4, 0, 0), Piece(Color.BLACK, PieceType.ROOK))
    board.place(Square4D(0, 7, 7, 7), _king(Color.BLACK))
    state = GameState(
        board=board,
        side_to_move=Color.WHITE,
        ep_target=Square4D(4, 5, 0, 0),
        ep_victim=Square4D(4, 4, 0, 0),
        ep_axis=PawnAxis.Y,
    )
    with pytest.raises(IllegalMoveError):
        state.push(
            Move4D(Square4D(3, 4, 0, 0), Square4D(4, 5, 0, 0), is_en_passant=True)
        )


# --- ep does not affect castling rights -----------------------------------


def test_en_passant_does_not_change_castling_rights() -> None:
    """Pawns don't interact with castling rights; ep is no exception."""
    state = _empty_game(Color.WHITE)
    state.board.place(Square4D(3, 4, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    state.board.place(Square4D(4, 6, 0, 0), _pawn(Color.BLACK, PawnAxis.Y))
    state.side_to_move = Color.BLACK
    state.push(Move4D(Square4D(4, 6, 0, 0), Square4D(4, 4, 0, 0)))
    rights_before = state.castling_rights
    state.push(
        Move4D(Square4D(3, 4, 0, 0), Square4D(4, 5, 0, 0), is_en_passant=True)
    )
    assert state.castling_rights == rights_before
