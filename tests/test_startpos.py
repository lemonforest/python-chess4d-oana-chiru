"""Starting-position tests (paper §3.3).

Citations refer to Oana & Chiru, *A Mathematical Framework for
Four-Dimensional Chess*, MDPI AppliedMath 6(3):48, 2026
(DOI 10.3390/appliedmath6030048).

Covers the slice classification arithmetic, the 896-piece total with
per-color / per-king counts, the 2D back-rank layout inside each
populated slice, and the invariant that the starting position is
neither in check nor terminal.
"""

from __future__ import annotations

from chess4d import BOARD_SIZE, Color, GameState, PawnAxis, Piece, PieceType, Square4D
from chess4d.startpos import (
    BLACK_ONLY_SLICES,
    CENTRAL_SLICES,
    EMPTY_SLICES,
    WHITE_ONLY_SLICES,
    initial_position,
)


# --- slice-set arithmetic (paper §3.3) -------------------------------------


def test_slice_set_sizes() -> None:
    assert len(CENTRAL_SLICES) == 4
    assert len(WHITE_ONLY_SLICES) == 24
    assert len(BLACK_ONLY_SLICES) == 24
    assert len(EMPTY_SLICES) == 12


def test_slice_sets_are_pairwise_disjoint() -> None:
    assert CENTRAL_SLICES.isdisjoint(WHITE_ONLY_SLICES)
    assert CENTRAL_SLICES.isdisjoint(BLACK_ONLY_SLICES)
    assert CENTRAL_SLICES.isdisjoint(EMPTY_SLICES)
    assert WHITE_ONLY_SLICES.isdisjoint(BLACK_ONLY_SLICES)
    assert WHITE_ONLY_SLICES.isdisjoint(EMPTY_SLICES)
    assert BLACK_ONLY_SLICES.isdisjoint(EMPTY_SLICES)


def test_slice_sets_union_covers_all_64_pairs() -> None:
    all_pairs = {(z, w) for z in range(BOARD_SIZE) for w in range(BOARD_SIZE)}
    union = CENTRAL_SLICES | WHITE_ONLY_SLICES | BLACK_ONLY_SLICES | EMPTY_SLICES
    assert union == all_pairs


def test_black_only_is_conjugate_of_white_only() -> None:
    """Swapping the ``w`` partition on each ``z``-band between W_only and
    B_only should recover the opposite set — catches off-by-one in the
    B_only definition against the paper's symmetric layout."""
    # Each white-only (z, w) has a black-only partner at (z, w') where
    # w' lies in the complementary half of the w-axis on the same z-band.
    for z, w in WHITE_ONLY_SLICES:
        if z in (0, 1, 2):
            # white-only lower-z band has w in {0,1,2,3}; black-only has {4..7}
            for w_other in (4, 5, 6, 7):
                assert (z, w_other) in BLACK_ONLY_SLICES
        else:
            assert z in (5, 6, 7)
            for w_other in (0, 1, 2, 3):
                assert (z, w_other) in BLACK_ONLY_SLICES


# --- overall piece counts (paper §3.3) -------------------------------------


def test_total_piece_count_is_896() -> None:
    state = initial_position()
    white = list(state.board.pieces_of(Color.WHITE))
    black = list(state.board.pieces_of(Color.BLACK))
    assert len(white) + len(black) == 896


def test_per_color_piece_count_is_448() -> None:
    state = initial_position()
    assert len(list(state.board.pieces_of(Color.WHITE))) == 448
    assert len(list(state.board.pieces_of(Color.BLACK))) == 448


def test_per_color_king_count_is_28() -> None:
    state = initial_position()
    white_kings = [
        sq for sq, p in state.board.pieces_of(Color.WHITE) if p.piece_type is PieceType.KING
    ]
    black_kings = [
        sq for sq, p in state.board.pieces_of(Color.BLACK) if p.piece_type is PieceType.KING
    ]
    assert len(white_kings) == 28
    assert len(black_kings) == 28


def test_every_pawn_is_y_oriented() -> None:
    """Paper §3.3: the initial position places Y-oriented pawns only;
    W-oriented pawns arise only via later placement/promotion rules."""
    state = initial_position()
    for color in (Color.WHITE, Color.BLACK):
        for _sq, piece in state.board.pieces_of(color):
            if piece.piece_type is PieceType.PAWN:
                assert piece.pawn_axis is PawnAxis.Y


# --- per-slice spot checks -------------------------------------------------


def _pieces_on_slice(state: GameState, z: int, w: int) -> list[tuple[Square4D, Piece]]:
    out: list[tuple[Square4D, Piece]] = []
    for color in (Color.WHITE, Color.BLACK):
        for sq, piece in state.board.pieces_of(color):
            if sq.z == z and sq.w == w:
                out.append((sq, piece))
    return out


def test_central_slice_has_both_colors_32_pieces() -> None:
    state = initial_position()
    # Pick the canonical central slice (3, 3).
    z, w = 3, 3
    assert (z, w) in CENTRAL_SLICES
    pieces = _pieces_on_slice(state, z, w)
    assert len(pieces) == 32
    colors = {p.color for _sq, p in pieces}
    assert colors == {Color.WHITE, Color.BLACK}


def test_white_only_slice_has_16_white_pieces_and_no_black() -> None:
    state = initial_position()
    z, w = 0, 0
    assert (z, w) in WHITE_ONLY_SLICES
    pieces = _pieces_on_slice(state, z, w)
    assert len(pieces) == 16
    assert all(p.color is Color.WHITE for _sq, p in pieces)


def test_black_only_slice_has_16_black_pieces_and_no_white() -> None:
    state = initial_position()
    z, w = 0, 4
    assert (z, w) in BLACK_ONLY_SLICES
    pieces = _pieces_on_slice(state, z, w)
    assert len(pieces) == 16
    assert all(p.color is Color.BLACK for _sq, p in pieces)


def test_empty_slice_has_no_pieces() -> None:
    state = initial_position()
    z, w = 3, 0
    assert (z, w) in EMPTY_SLICES
    assert _pieces_on_slice(state, z, w) == []


# --- back-rank layout (paper §3.3) -----------------------------------------


def test_white_back_rank_layout_in_a_populated_slice() -> None:
    """White back rank at y=0 is R N B Q K B N R (§3.3)."""
    state = initial_position()
    z, w = 0, 0  # white-only slice
    expected = (
        PieceType.ROOK,
        PieceType.KNIGHT,
        PieceType.BISHOP,
        PieceType.QUEEN,
        PieceType.KING,
        PieceType.BISHOP,
        PieceType.KNIGHT,
        PieceType.ROOK,
    )
    for x, pt in enumerate(expected):
        piece = state.board.occupant(Square4D(x, 0, z, w))
        assert piece is not None
        assert piece.color is Color.WHITE
        assert piece.piece_type is pt


def test_white_pawn_row_in_a_populated_slice() -> None:
    state = initial_position()
    z, w = 0, 0
    for x in range(BOARD_SIZE):
        piece = state.board.occupant(Square4D(x, 1, z, w))
        assert piece is not None
        assert piece.color is Color.WHITE
        assert piece.piece_type is PieceType.PAWN
        assert piece.pawn_axis is PawnAxis.Y


def test_black_back_rank_layout_in_a_populated_slice() -> None:
    state = initial_position()
    z, w = 0, 4  # black-only slice
    expected = (
        PieceType.ROOK,
        PieceType.KNIGHT,
        PieceType.BISHOP,
        PieceType.QUEEN,
        PieceType.KING,
        PieceType.BISHOP,
        PieceType.KNIGHT,
        PieceType.ROOK,
    )
    for x, pt in enumerate(expected):
        piece = state.board.occupant(Square4D(x, BOARD_SIZE - 1, z, w))
        assert piece is not None
        assert piece.color is Color.BLACK
        assert piece.piece_type is pt


def test_black_pawn_row_in_a_populated_slice() -> None:
    state = initial_position()
    z, w = 0, 4
    for x in range(BOARD_SIZE):
        piece = state.board.occupant(Square4D(x, BOARD_SIZE - 2, z, w))
        assert piece is not None
        assert piece.color is Color.BLACK
        assert piece.piece_type is PieceType.PAWN
        assert piece.pawn_axis is PawnAxis.Y


def test_central_slice_contains_both_back_ranks() -> None:
    """A central slice has white at y=0/1 AND black at y=6/7 simultaneously."""
    state = initial_position()
    z, w = 4, 4
    assert (z, w) in CENTRAL_SLICES
    # White king at (4, 0, 4, 4).
    white_k = state.board.occupant(Square4D(4, 0, z, w))
    assert white_k is not None
    assert white_k.color is Color.WHITE
    assert white_k.piece_type is PieceType.KING
    # Black king at (4, 7, 4, 4).
    black_k = state.board.occupant(Square4D(4, BOARD_SIZE - 1, z, w))
    assert black_k is not None
    assert black_k.color is Color.BLACK
    assert black_k.piece_type is PieceType.KING


# --- game-state invariants at t=0 ------------------------------------------


def test_initial_side_to_move_is_white() -> None:
    assert initial_position().side_to_move is Color.WHITE


def test_initial_position_is_not_in_check() -> None:
    assert not initial_position().in_check()


def test_initial_position_is_not_checkmate() -> None:
    assert not initial_position().is_checkmate()


def test_initial_position_is_not_stalemate() -> None:
    assert not initial_position().is_stalemate()


def test_initial_position_has_legal_moves() -> None:
    """Smoke: white has at least one legal move at t=0. No exact-count
    assertion — that would be a performance tripwire and is out of scope
    for Phase 4."""
    state = initial_position()
    gen = state.legal_moves()
    first = next(gen, None)
    assert first is not None
