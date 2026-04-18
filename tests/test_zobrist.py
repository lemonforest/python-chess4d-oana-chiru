"""Zobrist-hashing tests (paper §4.7).

Verifies that :func:`chess4d.zobrist.hash_position` distinguishes
every component of the position it is supposed to encode (placement,
pawn axis, side-to-move, castling rights, en-passant target) and
agrees under independent reconstruction.
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


def _kings_only(side: Color = Color.WHITE) -> GameState:
    board = Board4D()
    board.place(Square4D(0, 0, 7, 7), _king(Color.WHITE))
    board.place(Square4D(7, 7, 7, 7), _king(Color.BLACK))
    return GameState(board=board, side_to_move=side)


# --- reproducibility -------------------------------------------------------


def test_two_initial_positions_have_equal_hash() -> None:
    """Independently-constructed starting positions hash identically."""
    assert hash_position(initial_position()) == hash_position(initial_position())


def test_hash_is_deterministic_across_calls() -> None:
    state = initial_position()
    assert hash_position(state) == hash_position(state)


# --- placement distinguishes ---------------------------------------------


def test_different_placements_produce_different_hashes() -> None:
    """Fifty hand-built placements all produce distinct hashes."""
    hashes: set[int] = set()
    # Vary (x, y) for a white rook over a 7x8 grid on slice (0, 0) — 56 placements.
    # Using a single rook (not king) so we don't need to keep kings in bounds.
    for x in range(7):
        for y in range(8):
            board = Board4D()
            board.place(Square4D(0, 0, 7, 7), _king(Color.WHITE))
            board.place(Square4D(7, 7, 7, 7), _king(Color.BLACK))
            # Avoid the two king squares.
            if (x, y, 0, 0) in {(0, 0, 7, 7), (7, 7, 7, 7)}:
                continue
            board.place(Square4D(x, y, 0, 0), _white(PieceType.ROOK))
            state = GameState(board=board, side_to_move=Color.WHITE)
            hashes.add(hash_position(state))
    assert len(hashes) >= 50  # all distinct


# --- side-to-move ---------------------------------------------------------


def test_side_to_move_changes_hash() -> None:
    white_to_move = _kings_only(Color.WHITE)
    black_to_move = _kings_only(Color.BLACK)
    assert hash_position(white_to_move) != hash_position(black_to_move)


# --- castling rights ------------------------------------------------------


def test_castling_rights_change_hash() -> None:
    base = _kings_only()
    with_rights = _kings_only()
    with_rights.castling_rights = frozenset(
        {(Color.WHITE, 0, 0, CastleSide.KINGSIDE)}
    )
    assert hash_position(base) != hash_position(with_rights)


def test_different_castling_right_sets_differ() -> None:
    a = _kings_only()
    a.castling_rights = frozenset({(Color.WHITE, 0, 0, CastleSide.KINGSIDE)})
    b = _kings_only()
    b.castling_rights = frozenset({(Color.WHITE, 0, 0, CastleSide.QUEENSIDE)})
    assert hash_position(a) != hash_position(b)


# --- en-passant target ----------------------------------------------------


def test_ep_target_changes_hash() -> None:
    base = _kings_only()
    with_ep = _kings_only()
    with_ep.ep_target = Square4D(3, 5, 0, 0)
    with_ep.ep_victim = Square4D(3, 4, 0, 0)
    with_ep.ep_axis = PawnAxis.Y
    assert hash_position(base) != hash_position(with_ep)


# --- pawn axis in hash ----------------------------------------------------


def test_pawn_axis_distinguishes_hash() -> None:
    """A Y-pawn and a W-pawn on the same square hash differently."""
    a = _kings_only()
    a.board.place(Square4D(3, 1, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    b = _kings_only()
    b.board.place(Square4D(3, 1, 0, 0), _pawn(Color.WHITE, PawnAxis.W))
    assert hash_position(a) != hash_position(b)


# --- halfmove clock does NOT affect hash ----------------------------------


def test_halfmove_clock_does_not_affect_hash() -> None:
    """Halfmove clock is a draw-claim counter, not part of position identity."""
    a = _kings_only()
    b = _kings_only()
    b.halfmove_clock = 42
    assert hash_position(a) == hash_position(b)


# --- push/pop round-trip --------------------------------------------------


def test_push_pop_returns_to_same_hash() -> None:
    state = _kings_only()
    state.board.place(Square4D(0, 0, 0, 0), _white(PieceType.ROOK))
    state.board.place(Square4D(0, 7, 0, 0), _black(PieceType.ROOK))
    initial = hash_position(state)
    state.push(Move4D(Square4D(0, 0, 0, 0), Square4D(5, 0, 0, 0)))
    state.push(Move4D(Square4D(0, 7, 0, 0), Square4D(5, 7, 0, 0)))
    assert hash_position(state) != initial
    state.pop()
    state.pop()
    assert hash_position(state) == initial


def test_push_advances_position_history() -> None:
    state = _kings_only()
    state.board.place(Square4D(0, 0, 0, 0), _white(PieceType.ROOK))
    assert len(state.position_history) == 1
    state.push(Move4D(Square4D(0, 0, 0, 0), Square4D(5, 0, 0, 0)))
    assert len(state.position_history) == 2


def test_pop_rewinds_position_history() -> None:
    state = _kings_only()
    state.board.place(Square4D(0, 0, 0, 0), _white(PieceType.ROOK))
    state.push(Move4D(Square4D(0, 0, 0, 0), Square4D(5, 0, 0, 0)))
    state.pop()
    assert len(state.position_history) == 1
