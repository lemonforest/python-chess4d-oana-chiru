"""Phase 5 feature-interaction regression tests.

Goal: cover two-feature collisions that the single-feature test files
and the isolation-oriented ``test_phase5_smoke.py`` don't exercise.
The interaction matrix sections (A-L) correspond to
``hoodoos/brokenpaste.md``'s maintenance-pass outline.

Redundancy notes — skipped in favor of existing coverage:

* Section B1 "castling doesn't reset clock" — covered verbatim by
  :func:`test_fifty_move.test_castling_does_not_reset_clock`.
* Section D1 "ep resets clock" — covered verbatim by
  :func:`test_fifty_move.test_en_passant_capture_resets_clock`.
* Section E1 "ep_target changes hash" — covered at the unit level by
  :func:`test_zobrist.test_ep_target_changes_hash`; the interaction
  story here is Section E2 (gameplay flow), which is kept.
"""

from __future__ import annotations

import random
from typing import Optional

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from chess4d import (
    Board4D,
    CastleSide,
    CastlingRight,
    Color,
    GameState,
    IllegalMoveError,
    Move4D,
    PawnAxis,
    Piece,
    PieceType,
    Square4D,
    hash_position,
    initial_position,
)


# --- helpers ---------------------------------------------------------------


def _white(pt: PieceType) -> Piece:
    return Piece(Color.WHITE, pt)


def _black(pt: PieceType) -> Piece:
    return Piece(Color.BLACK, pt)


def _king(color: Color) -> Piece:
    return Piece(color, PieceType.KING)


def _pawn(color: Color, axis: PawnAxis) -> Piece:
    return Piece(color, PieceType.PAWN, axis)


def _clone_board(board: Board4D) -> Board4D:
    """Return a new :class:`Board4D` with the same placement as ``board``."""
    clone = Board4D()
    for color in Color:
        for sq, piece in board.pieces_of(color):
            clone.place(sq, piece)
    return clone


# =============================================================================
# Section A — Castling × En passant
# =============================================================================


def test_castling_clears_prior_ep_target() -> None:
    """A castling move clears any standing ep_target, like any non-two-step."""
    board = Board4D()
    board.place(Square4D(4, 0, 0, 0), _white(PieceType.KING))
    board.place(Square4D(7, 0, 0, 0), _white(PieceType.ROOK))
    board.place(Square4D(4, 7, 1, 0), _black(PieceType.KING))
    board.place(Square4D(3, 6, 1, 0), _pawn(Color.BLACK, PawnAxis.Y))
    state = GameState(
        board=board,
        side_to_move=Color.BLACK,
        castling_rights=frozenset(
            {(Color.WHITE, 0, 0, CastleSide.KINGSIDE)}
        ),
    )
    # Ply 1 (B): two-step arms ep.
    state.push(Move4D(Square4D(3, 6, 1, 0), Square4D(3, 4, 1, 0)))
    assert state.ep_target is not None
    # Ply 2 (W): castle kingside on slice (0, 0) — unrelated to the ep state.
    state.push(
        Move4D(Square4D(4, 0, 0, 0), Square4D(6, 0, 0, 0), is_castling=True)
    )
    assert state.ep_target is None
    assert state.ep_victim is None
    assert state.ep_axis is None


def test_two_step_then_castle_then_pop_restores_ep_state() -> None:
    """Pop after castle restores ep_target set by the prior two-step."""
    board = Board4D()
    board.place(Square4D(4, 0, 0, 0), _white(PieceType.KING))
    board.place(Square4D(7, 0, 0, 0), _white(PieceType.ROOK))
    board.place(Square4D(4, 7, 1, 0), _black(PieceType.KING))
    board.place(Square4D(3, 6, 1, 0), _pawn(Color.BLACK, PawnAxis.Y))
    state = GameState(
        board=board,
        side_to_move=Color.BLACK,
        castling_rights=frozenset(
            {(Color.WHITE, 0, 0, CastleSide.KINGSIDE)}
        ),
    )
    state.push(Move4D(Square4D(3, 6, 1, 0), Square4D(3, 4, 1, 0)))
    ep_target_after_twostep = state.ep_target
    ep_victim_after_twostep = state.ep_victim
    ep_axis_after_twostep = state.ep_axis
    state.push(
        Move4D(Square4D(4, 0, 0, 0), Square4D(6, 0, 0, 0), is_castling=True)
    )
    state.pop()
    assert state.ep_target == ep_target_after_twostep
    assert state.ep_victim == ep_victim_after_twostep
    assert state.ep_axis == ep_axis_after_twostep


def test_ep_capture_does_not_spuriously_revoke_home_rook_right() -> None:
    """An ep capture adjacent to a home-square rook leaves that rook's right.

    ``_rook_home_right`` only fires when the captured piece is a rook
    on its home square; pawns aren't rooks. This is a regression guard
    against accidentally widening the revocation predicate.
    """
    board = Board4D()
    board.place(Square4D(0, 0, 7, 7), _king(Color.WHITE))
    board.place(Square4D(7, 7, 7, 7), _king(Color.BLACK))
    # White kingside home rook — its right should be preserved.
    board.place(Square4D(7, 0, 0, 0), _white(PieceType.ROOK))
    # Y-pawns primed for ep.
    board.place(Square4D(3, 4, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    board.place(Square4D(4, 6, 0, 0), _pawn(Color.BLACK, PawnAxis.Y))
    rights = frozenset({(Color.WHITE, 0, 0, CastleSide.KINGSIDE)})
    state = GameState(
        board=board, side_to_move=Color.BLACK, castling_rights=rights
    )
    state.push(Move4D(Square4D(4, 6, 0, 0), Square4D(4, 4, 0, 0)))
    state.push(
        Move4D(
            Square4D(3, 4, 0, 0),
            Square4D(4, 5, 0, 0),
            is_en_passant=True,
        )
    )
    assert state.castling_rights == rights


# =============================================================================
# Section B — Castling × Halfmove clock
# B1 is covered by test_fifty_move.test_castling_does_not_reset_clock.
# =============================================================================


def test_castling_undo_restores_halfmove_clock_exactly() -> None:
    board = Board4D()
    board.place(Square4D(4, 0, 0, 0), _white(PieceType.KING))
    board.place(Square4D(7, 0, 0, 0), _white(PieceType.ROOK))
    board.place(Square4D(0, 0, 7, 7), _king(Color.BLACK))
    state = GameState(
        board=board,
        side_to_move=Color.WHITE,
        castling_rights=frozenset(
            {(Color.WHITE, 0, 0, CastleSide.KINGSIDE)}
        ),
        halfmove_clock=33,
    )
    state.push(
        Move4D(Square4D(4, 0, 0, 0), Square4D(6, 0, 0, 0), is_castling=True)
    )
    assert state.halfmove_clock == 34
    state.pop()
    assert state.halfmove_clock == 33


# =============================================================================
# Section C — Castling × Threefold repetition
# =============================================================================


def test_king_move_loses_both_rights_distinguishes_placement_repeat() -> None:
    """A king's earlier move revokes both rights on its slice; the placement
    may repeat but the hash must not, so the position is not a repeat.
    """
    board = Board4D()
    board.place(Square4D(4, 0, 0, 0), _white(PieceType.KING))
    board.place(Square4D(7, 0, 0, 0), _white(PieceType.ROOK))
    board.place(Square4D(0, 0, 7, 7), _king(Color.BLACK))
    board.place(Square4D(0, 7, 7, 7), _black(PieceType.ROOK))
    rights = frozenset(
        {
            (Color.WHITE, 0, 0, CastleSide.KINGSIDE),
            (Color.WHITE, 0, 0, CastleSide.QUEENSIDE),
        }
    )
    state = GameState(
        board=board, side_to_move=Color.WHITE, castling_rights=rights
    )
    initial_hash = hash_position(state)

    # King shuffles off home and back; each king move on the home slice
    # revokes BOTH rights on that slice (per _revoke_rights_for_move).
    state.push(Move4D(Square4D(4, 0, 0, 0), Square4D(4, 1, 0, 0)))  # W
    state.push(Move4D(Square4D(0, 7, 7, 7), Square4D(1, 7, 7, 7)))  # B
    state.push(Move4D(Square4D(4, 1, 0, 0), Square4D(4, 0, 0, 0)))  # W
    state.push(Move4D(Square4D(1, 7, 7, 7), Square4D(0, 7, 7, 7)))  # B

    assert state.castling_rights == frozenset()
    assert hash_position(state) != initial_hash
    assert not state.is_threefold_repetition()


def test_mirror_castles_on_different_slices_do_not_false_repeat() -> None:
    """White castles on S1 and black castles on S2; the resulting state is
    novel every time because rights shifted on each castle.
    """
    board = Board4D()
    # Two independent castling setups, one per side, on different slices.
    board.place(Square4D(4, 0, 0, 0), _white(PieceType.KING))
    board.place(Square4D(7, 0, 0, 0), _white(PieceType.ROOK))
    board.place(Square4D(4, 7, 1, 1), _black(PieceType.KING))
    board.place(Square4D(7, 7, 1, 1), _black(PieceType.ROOK))
    rights = frozenset(
        {
            (Color.WHITE, 0, 0, CastleSide.KINGSIDE),
            (Color.BLACK, 1, 1, CastleSide.KINGSIDE),
        }
    )
    state = GameState(
        board=board, side_to_move=Color.WHITE, castling_rights=rights
    )
    hashes_seen: list[int] = [hash_position(state)]

    state.push(
        Move4D(Square4D(4, 0, 0, 0), Square4D(6, 0, 0, 0), is_castling=True)
    )
    hashes_seen.append(hash_position(state))
    state.push(
        Move4D(Square4D(4, 7, 1, 1), Square4D(6, 7, 1, 1), is_castling=True)
    )
    hashes_seen.append(hash_position(state))

    # All three hashes should be distinct: different placements + shifting rights.
    assert len(set(hashes_seen)) == 3
    assert not state.is_threefold_repetition()


# =============================================================================
# Section D — En passant × Halfmove clock
# D1 is covered by test_fifty_move.test_en_passant_capture_resets_clock.
# =============================================================================


def test_ep_capture_undo_restores_halfmove_clock() -> None:
    board = Board4D()
    board.place(Square4D(0, 0, 7, 7), _king(Color.WHITE))
    board.place(Square4D(7, 7, 7, 7), _king(Color.BLACK))
    board.place(Square4D(3, 4, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    board.place(Square4D(4, 6, 0, 0), _pawn(Color.BLACK, PawnAxis.Y))
    state = GameState(
        board=board, side_to_move=Color.BLACK, halfmove_clock=25
    )
    # Black two-step resets clock to 0 (pawn move).
    state.push(Move4D(Square4D(4, 6, 0, 0), Square4D(4, 4, 0, 0)))
    clock_after_twostep = state.halfmove_clock
    # White ep capture — clock reset to 0 again (pawn + capture).
    state.push(
        Move4D(
            Square4D(3, 4, 0, 0),
            Square4D(4, 5, 0, 0),
            is_en_passant=True,
        )
    )
    assert state.halfmove_clock == 0
    state.pop()
    assert state.halfmove_clock == clock_after_twostep
    state.pop()
    assert state.halfmove_clock == 25


# =============================================================================
# Section E — En passant × Threefold repetition
# E1's hand-built case is in test_zobrist; this covers the gameplay flow.
# =============================================================================


def test_expired_ep_does_not_conflate_repetition() -> None:
    """The hash after a two-step (ep set) differs from the same placement
    reached later without an ep target — so the two states do not
    collapse together for repetition counting.
    """
    board = Board4D()
    board.place(Square4D(0, 0, 7, 7), _king(Color.WHITE))
    board.place(Square4D(7, 7, 7, 7), _king(Color.BLACK))
    board.place(Square4D(4, 6, 0, 0), _pawn(Color.BLACK, PawnAxis.Y))
    board.place(Square4D(0, 0, 0, 0), _white(PieceType.ROOK))
    board.place(Square4D(0, 7, 0, 0), _black(PieceType.ROOK))
    state = GameState(board=board, side_to_move=Color.BLACK)

    state.push(Move4D(Square4D(4, 6, 0, 0), Square4D(4, 4, 0, 0)))  # B two-step
    hash_with_ep = hash_position(state)
    assert state.ep_target is not None

    # White and black each shuffle a rook out and back; ep expires after the
    # first white reply and never re-arms (no further two-steps).
    state.push(Move4D(Square4D(0, 0, 0, 0), Square4D(5, 0, 0, 0)))  # W
    assert state.ep_target is None
    state.push(Move4D(Square4D(0, 7, 0, 0), Square4D(5, 7, 0, 0)))  # B
    state.push(Move4D(Square4D(5, 0, 0, 0), Square4D(0, 0, 0, 0)))  # W
    state.push(Move4D(Square4D(5, 7, 0, 0), Square4D(0, 7, 0, 0)))  # B
    hash_without_ep = hash_position(state)

    # Placement (including the black pawn at (4, 4, 0, 0)) matches the
    # post-two-step state, but ep_target differs → hashes differ.
    assert hash_with_ep != hash_without_ep


# =============================================================================
# Section F — Check × Castling
# =============================================================================


def _base_castling_position(
    extra: Optional[list[tuple[Square4D, Piece]]] = None,
) -> GameState:
    """Build a clean kingside-castling-ready position for white on slice (0,0).

    Extra pieces (attackers, blockers) are placed after the base setup.
    """
    board = Board4D()
    board.place(Square4D(4, 0, 0, 0), _white(PieceType.KING))
    board.place(Square4D(7, 0, 0, 0), _white(PieceType.ROOK))
    board.place(Square4D(0, 0, 7, 7), _king(Color.BLACK))
    if extra:
        for sq, piece in extra:
            board.place(sq, piece)
    return GameState(
        board=board,
        side_to_move=Color.WHITE,
        castling_rights=frozenset(
            {(Color.WHITE, 0, 0, CastleSide.KINGSIDE)}
        ),
    )


def test_cannot_castle_while_in_check() -> None:
    # Black rook on x=4 y-file attacks WK at (4, 0, 0, 0).
    state = _base_castling_position(
        extra=[(Square4D(4, 7, 0, 0), _black(PieceType.ROOK))]
    )
    assert state.in_check()
    with pytest.raises(IllegalMoveError):
        state.push(
            Move4D(
                Square4D(4, 0, 0, 0),
                Square4D(6, 0, 0, 0),
                is_castling=True,
            )
        )


def test_cannot_castle_through_square_attacked_from_other_slice() -> None:
    """§3.9 Def 10 clause 3 — the transit must be safe from any (z', w')."""
    # Black rook at (5, 0, 3, 0): z-ray passes through (5, 0, 0, 0),
    # which is white's kingside castling transit square. The attacker
    # sits on slice (3, 0), not the castling slice (0, 0).
    state = _base_castling_position(
        extra=[(Square4D(5, 0, 3, 0), _black(PieceType.ROOK))]
    )
    assert not state.in_check()  # WK at (4,0,0,0) not on the rook's rays.
    with pytest.raises(IllegalMoveError):
        state.push(
            Move4D(
                Square4D(4, 0, 0, 0),
                Square4D(6, 0, 0, 0),
                is_castling=True,
            )
        )


def test_cannot_castle_into_check() -> None:
    # Black rook at (6, 4, 0, 0) attacks destination (6, 0, 0, 0) along y.
    state = _base_castling_position(
        extra=[(Square4D(6, 4, 0, 0), _black(PieceType.ROOK))]
    )
    assert not state.in_check()
    with pytest.raises(IllegalMoveError):
        state.push(
            Move4D(
                Square4D(4, 0, 0, 0),
                Square4D(6, 0, 0, 0),
                is_castling=True,
            )
        )


def test_castling_legality_reevaluated_per_call() -> None:
    """Castling rights alone don't certify legality; transit safety is
    re-checked at push time even if rights have never been revoked.
    """
    # White bishop on (5, 1, 0, 0) currently blocks a black rook's y-ray.
    # After the bishop moves, the ray opens and (5, 0, 0, 0) is attacked.
    state = _base_castling_position(
        extra=[
            (Square4D(5, 1, 0, 0), _white(PieceType.BISHOP)),
            (Square4D(5, 4, 0, 0), _black(PieceType.ROOK)),
            (Square4D(0, 7, 7, 7), _black(PieceType.ROOK)),
        ]
    )
    # Before moving the bishop, castling is legal (listed in legal_moves).
    castling_move = Move4D(
        Square4D(4, 0, 0, 0), Square4D(6, 0, 0, 0), is_castling=True
    )
    assert castling_move in set(state.legal_moves())

    # Open the ray: W bishop steps off the file.
    state.push(Move4D(Square4D(5, 1, 0, 0), Square4D(6, 2, 0, 0)))
    # Black plays something irrelevant.
    state.push(Move4D(Square4D(0, 7, 7, 7), Square4D(1, 7, 7, 7)))

    # The castling right is still held — nothing revoked it.
    assert (Color.WHITE, 0, 0, CastleSide.KINGSIDE) in state.castling_rights
    # But castling is no longer legal: the transit square is attacked now.
    with pytest.raises(IllegalMoveError):
        state.push(castling_move)


# =============================================================================
# Section G — Check × En passant
# =============================================================================


def test_ep_capture_that_leaves_own_king_in_check_is_rejected() -> None:
    """Pinned-pawn en passant: capturing would expose the white king."""
    board = Board4D()
    # WK on x=0, rank 4; B rook on x=7, rank 4; W pawn between them at x=3.
    board.place(Square4D(0, 4, 0, 0), _king(Color.WHITE))
    board.place(Square4D(7, 4, 0, 0), _black(PieceType.ROOK))
    board.place(Square4D(3, 4, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    # B pawn ready for a two-step, B king faraway.
    board.place(Square4D(4, 6, 0, 0), _pawn(Color.BLACK, PawnAxis.Y))
    board.place(Square4D(7, 7, 7, 7), _king(Color.BLACK))
    state = GameState(board=board, side_to_move=Color.BLACK)

    state.push(Move4D(Square4D(4, 6, 0, 0), Square4D(4, 4, 0, 0)))  # B two-step
    assert state.ep_target == Square4D(4, 5, 0, 0)

    ep_move = Move4D(
        Square4D(3, 4, 0, 0),
        Square4D(4, 5, 0, 0),
        is_en_passant=True,
    )
    # Direct push: rejected (leaves WK in check via black rook's x-ray).
    with pytest.raises(IllegalMoveError):
        state.push(ep_move)
    # And legal_moves does not emit it.
    assert ep_move not in set(state.legal_moves())


def test_ep_capture_giving_check_is_legal() -> None:
    """An ep capture that lands adjacent to the enemy king delivers check."""
    board = Board4D()
    board.place(Square4D(0, 0, 7, 7), _king(Color.WHITE))
    # Black king positioned so that a white Y-pawn arriving at (4, 5, 0, 0)
    # attacks it (white Y-pawn attacks (x±1, y+1)).
    board.place(Square4D(5, 6, 0, 0), _king(Color.BLACK))
    board.place(Square4D(3, 4, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    board.place(Square4D(4, 6, 0, 0), _pawn(Color.BLACK, PawnAxis.Y))
    state = GameState(board=board, side_to_move=Color.BLACK)

    state.push(Move4D(Square4D(4, 6, 0, 0), Square4D(4, 4, 0, 0)))  # B two-step
    state.push(
        Move4D(
            Square4D(3, 4, 0, 0),
            Square4D(4, 5, 0, 0),
            is_en_passant=True,
        )
    )
    assert state.side_to_move == Color.BLACK
    assert state.in_check()


# =============================================================================
# Section H — Check × Threefold repetition
# =============================================================================


def test_check_and_threefold_are_independent_predicates() -> None:
    """in_check and is_threefold_repetition do not share state."""
    # Position A: in check, not threefold.
    board_a = Board4D()
    board_a.place(Square4D(0, 0, 0, 0), _king(Color.WHITE))
    board_a.place(Square4D(0, 7, 0, 0), _black(PieceType.ROOK))
    board_a.place(Square4D(7, 7, 7, 7), _king(Color.BLACK))
    a = GameState(board=board_a, side_to_move=Color.WHITE)
    assert a.in_check()
    assert not a.is_threefold_repetition()

    # Position B: not in check, but history is seeded to 3 occurrences.
    board_b = Board4D()
    board_b.place(Square4D(0, 0, 7, 7), _king(Color.WHITE))
    board_b.place(Square4D(7, 7, 7, 7), _king(Color.BLACK))
    b = GameState(board=board_b, side_to_move=Color.WHITE)
    # Seed history with 3 copies of the current hash via explicit construction.
    seeded_hash = hash_position(b)
    b.position_history.extend([seeded_hash, seeded_hash])
    assert not b.in_check()
    assert b.is_threefold_repetition()


def test_cycle_passing_through_check_triggers_threefold() -> None:
    """A shuffle cycle that repeatedly drops into an in-check position still
    counts as a repetition — the predicate does not filter out checks.
    """
    # Starting position: WK in check from BR along x-axis on rank 0.
    # The cycle requires BR to step aside (so WK can return safely) and
    # then return (re-establishing the check) — otherwise WK can never
    # re-enter the checked square.
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _king(Color.WHITE))
    board.place(Square4D(7, 0, 0, 0), _black(PieceType.ROOK))  # attacks y=0
    board.place(Square4D(7, 7, 0, 0), _king(Color.BLACK))
    state = GameState(board=board, side_to_move=Color.WHITE)
    assert state.in_check()

    # Cycle (4 plies): WK escapes, BR steps off the x-file, WK returns,
    # BR steps back onto it (restoring the check). Two cycles = 8 plies,
    # so the starting hash occurs 3 times (at plies 0, 4, 8).
    for _ in range(2):
        state.push(Move4D(Square4D(0, 0, 0, 0), Square4D(0, 1, 0, 0)))  # WK out
        state.push(Move4D(Square4D(7, 0, 0, 0), Square4D(7, 5, 0, 0)))  # BR aside
        state.push(Move4D(Square4D(0, 1, 0, 0), Square4D(0, 0, 0, 0)))  # WK back
        state.push(Move4D(Square4D(7, 5, 0, 0), Square4D(7, 0, 0, 0)))  # BR back
    assert state.in_check()
    assert state.is_threefold_repetition()


# =============================================================================
# Section I — Halfmove clock × Threefold repetition
# =============================================================================


def test_fifty_move_and_threefold_both_fire_simultaneously() -> None:
    """Two predicates are independent — both can fire at the same state."""
    board = Board4D()
    board.place(Square4D(0, 0, 7, 7), _king(Color.WHITE))
    board.place(Square4D(7, 7, 7, 7), _king(Color.BLACK))
    state = GameState(
        board=board, side_to_move=Color.WHITE, halfmove_clock=150
    )
    h = hash_position(state)
    state.position_history.extend([h, h])
    assert state.is_fifty_move_draw()
    assert state.is_threefold_repetition()


def test_pawn_move_resets_clock_but_history_keeps_growing() -> None:
    """Clock reset is orthogonal to history truncation."""
    board = Board4D()
    board.place(Square4D(0, 0, 7, 7), _king(Color.WHITE))
    board.place(Square4D(7, 7, 7, 7), _king(Color.BLACK))
    board.place(Square4D(3, 1, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    board.place(Square4D(0, 0, 0, 0), _white(PieceType.ROOK))
    board.place(Square4D(0, 7, 0, 0), _black(PieceType.ROOK))
    state = GameState(
        board=board, side_to_move=Color.WHITE, halfmove_clock=40
    )
    history_len_before = len(state.position_history)
    # Two non-resetting moves, then a pawn move (reset).
    state.push(Move4D(Square4D(0, 0, 0, 0), Square4D(5, 0, 0, 0)))  # W rook
    state.push(Move4D(Square4D(0, 7, 0, 0), Square4D(5, 7, 0, 0)))  # B rook
    assert state.halfmove_clock == 42
    state.push(Move4D(Square4D(3, 1, 0, 0), Square4D(3, 2, 0, 0)))  # W pawn
    assert state.halfmove_clock == 0
    # History grew by one entry per push regardless of clock resets.
    assert len(state.position_history) == history_len_before + 3


# =============================================================================
# Section J — Undo-stack depth stress
# =============================================================================


def test_long_castling_sequence_unwinds_to_initial_state() -> None:
    """Twenty castlings (10 white + 10 black, on disjoint slices) pushed
    then all popped — bit-identical state restored.

    White and black setups must live on disjoint ``(z, w)`` slices so that
    the post-castle white rook at ``(5, 0, z_w, w_w)`` does not attack the
    black-king transit square ``(5, 7, z_b, w_b)`` along the y-axis.
    """
    white_slices: list[tuple[int, int]] = [
        (z, w) for w in (0, 1) for z in range(5)
    ]
    black_slices: list[tuple[int, int]] = [
        (z, w) for w in (2, 3) for z in range(5)
    ]
    assert len(white_slices) == 10
    assert len(black_slices) == 10
    assert set(white_slices).isdisjoint(black_slices)

    board = Board4D()
    rights: set[CastlingRight] = set()
    for z, w in white_slices:
        board.place(Square4D(4, 0, z, w), _white(PieceType.KING))
        board.place(Square4D(7, 0, z, w), _white(PieceType.ROOK))
        rights.add((Color.WHITE, z, w, CastleSide.KINGSIDE))
    for z, w in black_slices:
        board.place(Square4D(4, 7, z, w), _black(PieceType.KING))
        board.place(Square4D(7, 7, z, w), _black(PieceType.ROOK))
        rights.add((Color.BLACK, z, w, CastleSide.KINGSIDE))
    state = GameState(
        board=board,
        side_to_move=Color.WHITE,
        castling_rights=frozenset(rights),
    )

    snapshot_board = _clone_board(state.board)
    snapshot_rights = state.castling_rights
    snapshot_history = list(state.position_history)

    for i in range(10):
        wz, ww = white_slices[i]
        bz, bw = black_slices[i]
        state.push(
            Move4D(
                Square4D(4, 0, wz, ww),
                Square4D(6, 0, wz, ww),
                is_castling=True,
            )
        )
        state.push(
            Move4D(
                Square4D(4, 7, bz, bw),
                Square4D(6, 7, bz, bw),
                is_castling=True,
            )
        )

    assert state.castling_rights == frozenset()

    for _ in range(20):
        state.pop()

    assert state.board == snapshot_board
    assert state.castling_rights == snapshot_rights
    assert state.position_history == snapshot_history
    assert state.side_to_move == Color.WHITE
    assert state.halfmove_clock == 0


def test_interleaved_ep_and_normal_pushes_unwind_cleanly() -> None:
    """Ten plies including an ep capture; after popping all, state matches."""
    board = Board4D()
    board.place(Square4D(0, 0, 7, 7), _king(Color.WHITE))
    board.place(Square4D(7, 7, 7, 7), _king(Color.BLACK))
    board.place(Square4D(3, 4, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    board.place(Square4D(4, 6, 0, 0), _pawn(Color.BLACK, PawnAxis.Y))
    board.place(Square4D(0, 3, 0, 0), _white(PieceType.ROOK))
    board.place(Square4D(0, 5, 0, 0), _black(PieceType.ROOK))
    state = GameState(board=board, side_to_move=Color.BLACK)

    snapshot_board = _clone_board(state.board)
    snapshot_rights = state.castling_rights
    snapshot_history = list(state.position_history)
    snapshot_clock = state.halfmove_clock
    snapshot_side = state.side_to_move

    plies: list[Move4D] = [
        Move4D(Square4D(0, 5, 0, 0), Square4D(5, 5, 0, 0)),  # B rook out
        Move4D(Square4D(0, 3, 0, 0), Square4D(5, 3, 0, 0)),  # W rook out
        Move4D(Square4D(5, 5, 0, 0), Square4D(0, 5, 0, 0)),  # B rook back
        Move4D(Square4D(5, 3, 0, 0), Square4D(0, 3, 0, 0)),  # W rook back
        Move4D(Square4D(4, 6, 0, 0), Square4D(4, 4, 0, 0)),  # B two-step
        Move4D(
            Square4D(3, 4, 0, 0),
            Square4D(4, 5, 0, 0),
            is_en_passant=True,
        ),
        Move4D(Square4D(0, 5, 0, 0), Square4D(1, 5, 0, 0)),  # B rook
        Move4D(Square4D(0, 3, 0, 0), Square4D(1, 3, 0, 0)),  # W rook
        Move4D(Square4D(1, 5, 0, 0), Square4D(0, 5, 0, 0)),  # B rook
        Move4D(Square4D(1, 3, 0, 0), Square4D(0, 3, 0, 0)),  # W rook
    ]
    for m in plies:
        state.push(m)
    for _ in plies:
        state.pop()

    assert state.board == snapshot_board
    assert state.castling_rights == snapshot_rights
    assert state.position_history == snapshot_history
    assert state.halfmove_clock == snapshot_clock
    assert state.side_to_move == snapshot_side


# =============================================================================
# Section K — Rights-revocation edge cases
# =============================================================================


def test_rook_leaving_and_returning_home_does_not_restore_right() -> None:
    board = Board4D()
    board.place(Square4D(4, 0, 0, 0), _white(PieceType.KING))
    board.place(Square4D(7, 0, 0, 0), _white(PieceType.ROOK))
    board.place(Square4D(0, 0, 7, 7), _king(Color.BLACK))
    board.place(Square4D(0, 7, 7, 7), _black(PieceType.ROOK))
    state = GameState(
        board=board,
        side_to_move=Color.WHITE,
        castling_rights=frozenset(
            {(Color.WHITE, 0, 0, CastleSide.KINGSIDE)}
        ),
    )
    state.push(Move4D(Square4D(7, 0, 0, 0), Square4D(7, 3, 0, 0)))  # W
    assert state.castling_rights == frozenset()
    state.push(Move4D(Square4D(0, 7, 7, 7), Square4D(1, 7, 7, 7)))  # B
    state.push(Move4D(Square4D(7, 3, 0, 0), Square4D(7, 0, 0, 0)))  # W (home)
    # Rook is back home, but the right stays revoked.
    assert state.castling_rights == frozenset()


def test_promoted_rook_on_former_home_square_does_not_regrant_right() -> None:
    """A pawn captures the home rook and promotes to rook on the same square;
    the associated castling right stays revoked.
    """
    board = Board4D()
    board.place(Square4D(0, 0, 7, 7), _king(Color.WHITE))
    board.place(Square4D(7, 7, 7, 7), _king(Color.BLACK))
    # White Y-pawn one diagonal away from black's kingside home rook.
    board.place(Square4D(6, 6, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    board.place(Square4D(7, 7, 0, 0), _black(PieceType.ROOK))
    rights = frozenset({(Color.BLACK, 0, 0, CastleSide.KINGSIDE)})
    state = GameState(
        board=board, side_to_move=Color.WHITE, castling_rights=rights
    )
    # Single move: pawn captures rook and promotes to rook on (7, 7, 0, 0).
    state.push(
        Move4D(
            Square4D(6, 6, 0, 0),
            Square4D(7, 7, 0, 0),
            promotion=PieceType.ROOK,
        )
    )
    # Black's kingside right on slice (0, 0) is revoked (rook captured on home).
    assert state.castling_rights == frozenset()
    # The square now holds a white rook; it cannot grant anything to black.
    assert state.board.occupant(Square4D(7, 7, 0, 0)) == _white(PieceType.ROOK)
    # Popping restores the pre-capture state (right and rook).
    state.pop()
    assert state.castling_rights == rights
    assert state.board.occupant(Square4D(7, 7, 0, 0)) == _black(PieceType.ROOK)


# =============================================================================
# Section L — Hypothesis push-pop round-trip from the initial position
#
# Marked `slow` because each generated move requires a legal_moves() call on
# the 896-piece starting position, which is multi-second pre-Phase-6. Run
# explicitly with `pytest -m slow`.
# =============================================================================


@pytest.mark.slow
@settings(
    max_examples=3,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(seed=st.integers(min_value=0, max_value=2**32 - 1))
def test_push_pop_round_trip_from_initial_position_property(seed: int) -> None:
    """Random legal-move walk from the initial position, then full unwind."""
    state = initial_position()
    rng = random.Random(seed)
    n_plies = rng.randint(3, 6)

    snapshot_board = _clone_board(state.board)
    snapshot_side = state.side_to_move
    snapshot_rights = state.castling_rights
    snapshot_ep = (state.ep_target, state.ep_victim, state.ep_axis)
    snapshot_clock = state.halfmove_clock
    snapshot_history = list(state.position_history)

    pushed = 0
    for _ in range(n_plies):
        legal = list(state.legal_moves())
        if not legal:
            break
        state.push(rng.choice(legal))
        pushed += 1

    for _ in range(pushed):
        state.pop()

    assert state.board == snapshot_board
    assert state.side_to_move == snapshot_side
    assert state.castling_rights == snapshot_rights
    assert (state.ep_target, state.ep_victim, state.ep_axis) == snapshot_ep
    assert state.halfmove_clock == snapshot_clock
    assert state.position_history == snapshot_history
