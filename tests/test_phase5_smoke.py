"""Phase 5 integration smoke tests.

End-to-end exercises that touch multiple Phase 5 features at once:
castling, en passant, halfmove clock, and Zobrist repetition. Unit
tests for each feature live in their own files; this module verifies
they compose correctly.
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
    hash_position,
    initial_position,
)


def _white(pt: PieceType) -> Piece:
    return Piece(Color.WHITE, pt)


def _black(pt: PieceType) -> Piece:
    return Piece(Color.BLACK, pt)


def _king(color: Color) -> Piece:
    return Piece(color, PieceType.KING)


def _pawn(color: Color, axis: PawnAxis) -> Piece:
    return Piece(color, PieceType.PAWN, axis)


# --- full castling game ----------------------------------------------------


def test_full_castling_game_with_blockers_and_round_trip() -> None:
    """Clear a blocked kingside castling path, castle, then pop everything."""
    board = Board4D()
    board.place(Square4D(4, 0, 0, 0), _white(PieceType.KING))
    board.place(Square4D(7, 0, 0, 0), _white(PieceType.ROOK))  # castling rook
    board.place(Square4D(5, 0, 0, 0), _white(PieceType.ROOK))  # blocker (not home)
    board.place(Square4D(6, 0, 0, 0), _white(PieceType.ROOK))  # blocker (not home)
    board.place(Square4D(0, 0, 7, 7), _king(Color.BLACK))
    board.place(Square4D(0, 7, 7, 7), _black(PieceType.ROOK))
    rights = frozenset({(Color.WHITE, 0, 0, CastleSide.KINGSIDE)})
    state = GameState(
        board=board, side_to_move=Color.WHITE, castling_rights=rights
    )

    initial_hash = hash_position(state)
    assert state.castling_rights == rights

    # Clear blockers with alternating moves.
    state.push(Move4D(Square4D(5, 0, 0, 0), Square4D(5, 3, 0, 0)))  # W
    state.push(Move4D(Square4D(0, 7, 7, 7), Square4D(1, 7, 7, 7)))  # B
    state.push(Move4D(Square4D(6, 0, 0, 0), Square4D(6, 3, 0, 0)))  # W
    state.push(Move4D(Square4D(1, 7, 7, 7), Square4D(0, 7, 7, 7)))  # B
    # Castling rights still present — no rook-home move yet.
    assert state.castling_rights == rights

    state.push(
        Move4D(Square4D(4, 0, 0, 0), Square4D(6, 0, 0, 0), is_castling=True)
    )
    # Post-castle: king and castling rook have swapped past each other.
    assert state.board.occupant(Square4D(6, 0, 0, 0)) == _white(PieceType.KING)
    assert state.board.occupant(Square4D(5, 0, 0, 0)) == _white(PieceType.ROOK)
    assert state.board.occupant(Square4D(4, 0, 0, 0)) is None
    assert state.board.occupant(Square4D(7, 0, 0, 0)) is None
    # Right is revoked.
    assert state.castling_rights == frozenset()

    # Round-trip: pop all five plies.
    for _ in range(5):
        state.pop()
    assert hash_position(state) == initial_hash
    assert state.castling_rights == rights
    assert state.board.occupant(Square4D(4, 0, 0, 0)) == _white(PieceType.KING)
    assert state.board.occupant(Square4D(7, 0, 0, 0)) == _white(PieceType.ROOK)


# --- en passant + halfmove clock interaction ------------------------------


def test_en_passant_and_halfmove_clock_interact_correctly() -> None:
    """Two-step resets, en passant resets, non-pawn non-capture ticks."""
    board = Board4D()
    board.place(Square4D(0, 0, 7, 7), _king(Color.WHITE))
    board.place(Square4D(7, 7, 7, 7), _king(Color.BLACK))
    board.place(Square4D(3, 4, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    board.place(Square4D(4, 6, 0, 0), _pawn(Color.BLACK, PawnAxis.Y))
    board.place(Square4D(0, 0, 0, 0), _white(PieceType.ROOK))
    board.place(Square4D(0, 7, 0, 0), _black(PieceType.ROOK))
    state = GameState(
        board=board, side_to_move=Color.BLACK, halfmove_clock=17
    )

    # Ply 1 (B): pawn two-step resets clock and arms ep.
    state.push(Move4D(Square4D(4, 6, 0, 0), Square4D(4, 4, 0, 0)))
    assert state.halfmove_clock == 0
    assert state.ep_target == Square4D(4, 5, 0, 0)

    # Ply 2 (W): en-passant capture — pawn move AND capture, still resets.
    state.push(
        Move4D(
            Square4D(3, 4, 0, 0),
            Square4D(4, 5, 0, 0),
            is_en_passant=True,
        )
    )
    assert state.halfmove_clock == 0
    assert state.ep_target is None
    # Victim pawn removed.
    assert state.board.occupant(Square4D(4, 4, 0, 0)) is None

    # Plies 3-5: non-pawn non-capture rook shuffles tick the clock.
    state.push(Move4D(Square4D(0, 7, 0, 0), Square4D(5, 7, 0, 0)))  # B
    assert state.halfmove_clock == 1
    state.push(Move4D(Square4D(0, 0, 0, 0), Square4D(5, 0, 0, 0)))  # W
    assert state.halfmove_clock == 2
    state.push(Move4D(Square4D(5, 7, 0, 0), Square4D(0, 7, 0, 0)))  # B
    assert state.halfmove_clock == 3


# --- repetition vs. castling rights ---------------------------------------


def test_placement_repeats_but_castling_rights_differ_blocks_repetition() -> None:
    """Same placement with different castling rights → different hash, not a repetition."""
    board = Board4D()
    board.place(Square4D(4, 0, 0, 0), _white(PieceType.KING))
    board.place(Square4D(7, 0, 0, 0), _white(PieceType.ROOK))
    board.place(Square4D(0, 0, 7, 7), _king(Color.BLACK))
    board.place(Square4D(0, 7, 7, 7), _black(PieceType.ROOK))
    rights = frozenset({(Color.WHITE, 0, 0, CastleSide.KINGSIDE)})
    state = GameState(
        board=board, side_to_move=Color.WHITE, castling_rights=rights
    )
    initial_hash = hash_position(state)

    # Move white's kingside rook off home, move black's rook out,
    # return both rooks to home. Placement returns to initial; white's
    # kingside right is revoked because the rook left home.
    state.push(Move4D(Square4D(7, 0, 0, 0), Square4D(7, 3, 0, 0)))  # W
    state.push(Move4D(Square4D(0, 7, 7, 7), Square4D(1, 7, 7, 7)))  # B
    state.push(Move4D(Square4D(7, 3, 0, 0), Square4D(7, 0, 0, 0)))  # W
    state.push(Move4D(Square4D(1, 7, 7, 7), Square4D(0, 7, 7, 7)))  # B

    # Placement is bit-identical to the start.
    assert state.board.occupant(Square4D(7, 0, 0, 0)) == _white(PieceType.ROOK)
    assert state.board.occupant(Square4D(0, 7, 7, 7)) == _black(PieceType.ROOK)
    assert state.side_to_move == Color.WHITE
    # But castling rights are gone.
    assert state.castling_rights == frozenset()
    # Hence the hash differs and repetition does NOT count.
    assert hash_position(state) != initial_hash
    assert not state.is_threefold_repetition()


# --- initial position sanity ----------------------------------------------


def test_initial_position_has_legal_moves() -> None:
    """``initial_position().legal_moves()`` yields at least one candidate."""
    state = initial_position()
    gen = state.legal_moves()
    first = next(gen, None)
    assert first is not None
    assert not state.in_check()
    assert not state.is_checkmate()
    assert not state.is_stalemate()
    assert not state.is_fifty_move_draw()
    assert not state.is_threefold_repetition()
