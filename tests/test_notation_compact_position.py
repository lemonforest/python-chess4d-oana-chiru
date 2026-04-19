"""Phase 7B — compact position notation parse/render/round-trip."""

from __future__ import annotations

import pytest

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
)
from chess4d.notation import (
    NotationError,
    parse_compact_position,
    render_compact_position,
)
from chess4d.startpos import initial_position

# Round-trip: the real starting position ------------------------------------


def test_round_trip_initial_position() -> None:
    gs = initial_position()
    s = render_compact_position(gs)
    gs2 = parse_compact_position(s)
    assert gs2.board == gs.board
    assert gs2.side_to_move is gs.side_to_move
    assert gs2.castling_rights == gs.castling_rights
    assert gs2.ep_target == gs.ep_target
    assert gs2.ep_victim == gs.ep_victim
    assert gs2.ep_axis == gs.ep_axis
    assert gs2.halfmove_clock == gs.halfmove_clock


def test_initial_position_header_encodes_all_112_rights() -> None:
    gs = initial_position()
    header_line = render_compact_position(gs).split("\n", 1)[0]
    rights_tok = header_line.split(" ")[1]
    assert rights_tok.count(",") == 111  # 112 tokens => 111 commas


def test_initial_position_omits_12_empty_slices() -> None:
    gs = initial_position()
    lines = render_compact_position(gs).split("\n")
    # 1 header + 52 populated slice lines (64 total minus 12 empty).
    assert len(lines) == 1 + 52


# Empty / sparse boards ------------------------------------------------------


def test_empty_board_is_just_header() -> None:
    gs = GameState(board=Board4D(), side_to_move=Color.WHITE)
    s = render_compact_position(gs)
    assert s == "w - - 0"
    gs2 = parse_compact_position(s)
    assert gs2.board == gs.board
    assert gs2.side_to_move is Color.WHITE
    assert gs2.castling_rights == frozenset()
    assert gs2.ep_target is None
    assert gs2.halfmove_clock == 0


def test_empty_board_header_only_eof_round_trips() -> None:
    s = "w - - 0"
    gs = parse_compact_position(s)
    assert gs.board == Board4D()
    assert render_compact_position(gs) == s


def test_single_piece_slice() -> None:
    board = Board4D()
    board.place(Square4D(3, 2, 1, 4), Piece(Color.BLACK, PieceType.KNIGHT))
    gs = GameState(board=board, side_to_move=Color.BLACK, halfmove_clock=7)
    s = render_compact_position(gs)
    gs2 = parse_compact_position(s)
    assert gs2.board == board
    assert gs2.side_to_move is Color.BLACK
    assert gs2.halfmove_clock == 7


# Castling rights -----------------------------------------------------------


def test_round_trip_partial_castling_rights() -> None:
    board = Board4D()
    gs = GameState(
        board=board,
        side_to_move=Color.WHITE,
        castling_rights=frozenset(
            [
                (Color.WHITE, 3, 3, CastleSide.KINGSIDE),
                (Color.BLACK, 2, 5, CastleSide.QUEENSIDE),
            ]
        ),
    )
    s = render_compact_position(gs)
    assert "Wd4K" in s
    assert "Bc6Q" in s
    gs2 = parse_compact_position(s)
    assert gs2.castling_rights == gs.castling_rights


def test_castling_rights_are_sorted_canonically() -> None:
    board = Board4D()
    rights_unsorted = frozenset(
        [
            (Color.BLACK, 3, 3, CastleSide.QUEENSIDE),
            (Color.WHITE, 0, 0, CastleSide.QUEENSIDE),
            (Color.WHITE, 0, 0, CastleSide.KINGSIDE),
        ]
    )
    gs = GameState(
        board=board, side_to_move=Color.WHITE, castling_rights=rights_unsorted
    )
    header = render_compact_position(gs).split("\n", 1)[0]
    rights_tok = header.split(" ")[1]
    assert rights_tok == "Wa1K,Wa1Q,Bd4Q"


# En passant ----------------------------------------------------------------


def test_round_trip_y_axis_ep_state() -> None:
    # White pushes a Y-pawn two squares from y=1 to y=3 on slice (2, 3).
    gs = initial_position()
    from_sq = Square4D(0, 1, 2, 3)
    to_sq = Square4D(0, 3, 2, 3)
    gs.push(Move4D(from_sq, to_sq))
    assert gs.ep_target == Square4D(0, 2, 2, 3)
    s = render_compact_position(gs)
    gs2 = parse_compact_position(s)
    assert gs2.ep_target == gs.ep_target
    assert gs2.ep_victim == gs.ep_victim
    assert gs2.ep_axis is PawnAxis.Y


def test_round_trip_w_axis_ep_state_manual() -> None:
    board = Board4D()
    # A single W-oriented black pawn in the middle of an otherwise empty board,
    # reachable ep-state: it just moved from w=6 to w=4, so ep_target at w=5.
    board.place(Square4D(4, 4, 3, 4), Piece(Color.BLACK, PieceType.PAWN, PawnAxis.W))
    gs = GameState(
        board=board,
        side_to_move=Color.WHITE,
        ep_target=Square4D(4, 4, 3, 5),
        ep_victim=Square4D(4, 4, 3, 4),
        ep_axis=PawnAxis.W,
    )
    s = render_compact_position(gs)
    gs2 = parse_compact_position(s)
    assert gs2.ep_target == gs.ep_target
    assert gs2.ep_victim == gs.ep_victim
    assert gs2.ep_axis is PawnAxis.W


def test_parse_ep_target_missing_victim_raises() -> None:
    # Header claims an ep_target but no adjacent pawn sits on the board.
    s = "w - a3c4 0"
    with pytest.raises(NotationError) as exc_info:
        parse_compact_position(s)
    assert "no adjacent enemy pawn" in str(exc_info.value)


# Handwritten / whitespace tolerance ----------------------------------------


def test_parse_tolerates_blank_lines_between_slices() -> None:
    raw = "\n".join(
        [
            "w - - 0",
            "",
            "a1: RNBQKBNR/YYYYYYYY/......../......../......../......../yyyyyyyy/rnbqkbnr",
            "",
            "",
            "a2: RNBQKBNR/YYYYYYYY/......../......../......../......../yyyyyyyy/rnbqkbnr",
        ]
    )
    gs = parse_compact_position(raw)
    assert gs.side_to_move is Color.WHITE
    # Two populated slices.
    assert sum(1 for _ in gs.board.pieces_of(Color.WHITE)) == 32
    assert sum(1 for _ in gs.board.pieces_of(Color.BLACK)) == 32


def test_parse_tolerates_trailing_whitespace() -> None:
    raw = "w - - 0   \na1: RNBQKBNR/YYYYYYYY/......../......../......../......../yyyyyyyy/rnbqkbnr  \n"
    gs = parse_compact_position(raw)
    assert sum(1 for _ in gs.board.pieces_of(Color.WHITE)) == 16


def test_parse_accepts_empty_slice_marker() -> None:
    raw = "w - - 0\na1: empty\n"
    gs = parse_compact_position(raw)
    assert gs.board == Board4D()


def test_parse_accepts_uppercase_side_char() -> None:
    gs = parse_compact_position("W - - 0")
    assert gs.side_to_move is Color.WHITE
    gs = parse_compact_position("B - - 0")
    assert gs.side_to_move is Color.BLACK


# Invalid inputs ------------------------------------------------------------


@pytest.mark.parametrize(
    ("bad", "fragment"),
    [
        ("", "no header"),
        ("   \n\n", "no header"),
        ("w -", "4 space-separated"),
        ("z - - 0", "'w' or 'b'"),
        ("w - - xyz", "decimal integer"),
        ("w - - -1", "non-negative"),
        ("w Wa1X - 0", "'K' or 'Q'"),
        ("w Xa1K - 0", "'W' or 'B'"),
        ("w Wa1 - 0", "4 characters"),
        ("w Wa1K,Wa1K - 0", "duplicate"),
        ("w - - 0\nxxx", "missing ':'"),
        ("w - - 0\na1a: RNBQKBNR/YYYYYYYY/......../......../......../......../yyyyyyyy/rnbqkbnr", "slice key must be 2"),
        ("w - - 0\na1: RNBQKBNR/YYYYYYYY", "8 ranks"),
        ("w - - 0\na1: RNBQKBNR/YYYYYYYY/......../......../......../......../yyyyyyyy/rnbqkbn", "8 characters"),
        ("w - - 0\na1: RNBQKBNR/YYYYYYYY/......../......../......../......../yyyyyyyy/ZZZZZZZZ", "unknown piece"),
        ("w - - 0\na1: empty\na1: empty", "more than once"),
    ],
)
def test_parse_invalid_raises(bad: str, fragment: str) -> None:
    with pytest.raises(NotationError) as exc_info:
        parse_compact_position(bad)
    assert fragment in str(exc_info.value), (
        f"expected fragment {fragment!r}, got {exc_info.value!s}"
    )


# Piece letters round-trip --------------------------------------------------


def test_all_piece_types_round_trip() -> None:
    board = Board4D()
    placements = [
        (Square4D(0, 0, 0, 0), Piece(Color.WHITE, PieceType.ROOK)),
        (Square4D(1, 0, 0, 0), Piece(Color.WHITE, PieceType.KNIGHT)),
        (Square4D(2, 0, 0, 0), Piece(Color.WHITE, PieceType.BISHOP)),
        (Square4D(3, 0, 0, 0), Piece(Color.WHITE, PieceType.QUEEN)),
        (Square4D(4, 0, 0, 0), Piece(Color.WHITE, PieceType.KING)),
        (Square4D(5, 0, 0, 0), Piece(Color.WHITE, PieceType.PAWN, PawnAxis.Y)),
        (Square4D(6, 0, 0, 0), Piece(Color.WHITE, PieceType.PAWN, PawnAxis.W)),
        (Square4D(0, 7, 0, 0), Piece(Color.BLACK, PieceType.ROOK)),
        (Square4D(1, 7, 0, 0), Piece(Color.BLACK, PieceType.KNIGHT)),
        (Square4D(2, 7, 0, 0), Piece(Color.BLACK, PieceType.BISHOP)),
        (Square4D(3, 7, 0, 0), Piece(Color.BLACK, PieceType.QUEEN)),
        (Square4D(4, 7, 0, 0), Piece(Color.BLACK, PieceType.KING)),
        (Square4D(5, 7, 0, 0), Piece(Color.BLACK, PieceType.PAWN, PawnAxis.Y)),
        (Square4D(6, 7, 0, 0), Piece(Color.BLACK, PieceType.PAWN, PawnAxis.W)),
    ]
    for sq, p in placements:
        board.place(sq, p)
    gs = GameState(board=board, side_to_move=Color.WHITE)
    gs2 = parse_compact_position(render_compact_position(gs))
    assert gs2.board == board


# Replay of a constructed mid-game position ---------------------------------


def test_round_trip_after_a_legal_move() -> None:
    gs = initial_position()
    # A white Y-pawn advance from slice (3, 3) — a central slice.
    gs.push(Move4D(Square4D(0, 1, 3, 3), Square4D(0, 3, 3, 3)))
    s = render_compact_position(gs)
    gs2 = parse_compact_position(s)
    assert gs2.board == gs.board
    assert gs2.side_to_move is Color.BLACK
    assert gs2.castling_rights == gs.castling_rights
    assert gs2.ep_target == gs.ep_target
    assert gs2.ep_axis is PawnAxis.Y
    assert gs2.halfmove_clock == gs.halfmove_clock
