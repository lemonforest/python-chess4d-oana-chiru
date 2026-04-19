"""Phase 7C — JSON format (moves and positions)."""

from __future__ import annotations

import pytest
from hypothesis import given, strategies as st

from chess4d import (
    BOARD_SIZE,
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
    parse_json_move,
    parse_json_position,
    render_json_move,
    render_json_position,
)
from chess4d.startpos import initial_position

# Move round-trip -----------------------------------------------------------

_coord = st.integers(min_value=0, max_value=BOARD_SIZE - 1)
_sq = st.builds(Square4D, _coord, _coord, _coord, _coord)
_promo = st.sampled_from(
    [PieceType.QUEEN, PieceType.ROOK, PieceType.BISHOP, PieceType.KNIGHT]
)


def test_move_round_trip_ordinary() -> None:
    m = Move4D(Square4D(0, 1, 2, 3), Square4D(0, 3, 2, 3))
    assert parse_json_move(render_json_move(m)) == m


def test_move_round_trip_promotion() -> None:
    m = Move4D(Square4D(0, 6, 2, 3), Square4D(0, 7, 2, 3), promotion=PieceType.KNIGHT)
    assert parse_json_move(render_json_move(m)) == m


def test_move_round_trip_en_passant() -> None:
    m = Move4D(Square4D(0, 4, 2, 3), Square4D(0, 5, 2, 3), is_en_passant=True)
    assert parse_json_move(render_json_move(m)) == m


def test_move_round_trip_castling() -> None:
    m = Move4D(Square4D(4, 0, 2, 3), Square4D(6, 0, 2, 3), is_castling=True)
    assert parse_json_move(render_json_move(m)) == m


@given(from_sq=_sq, to_sq=_sq)
def test_hypothesis_ordinary(from_sq: Square4D, to_sq: Square4D) -> None:
    m = Move4D(from_sq, to_sq)
    assert parse_json_move(render_json_move(m)) == m


@given(from_sq=_sq, to_sq=_sq, promo=_promo)
def test_hypothesis_promotion(
    from_sq: Square4D, to_sq: Square4D, promo: PieceType
) -> None:
    m = Move4D(from_sq, to_sq, promotion=promo)
    assert parse_json_move(render_json_move(m)) == m


def test_move_defaults_on_missing_optional_fields() -> None:
    js = '{"from":[0,0,0,0],"to":[0,1,0,0]}'
    m = parse_json_move(js)
    assert m.promotion is None
    assert not m.is_castling
    assert not m.is_en_passant


# Move invalid inputs -------------------------------------------------------


@pytest.mark.parametrize(
    ("bad", "fragment"),
    [
        ("not-json", "invalid JSON"),
        ('[]', "must be a JSON object"),
        ('{"from":[0,0,0,0]}', "missing required key 'to'"),
        ('{"to":[0,0,0,0]}', "missing required key 'from'"),
        ('{"from":"a1c4","to":[0,1,0,0]}', "must be a 4-element array"),
        ('{"from":[0,0,0],"to":[0,1,0,0]}', "4-element array"),
        ('{"from":[0,0,0,0,0],"to":[0,1,0,0]}', "4-element array"),
        ('{"from":[0,0,0,8],"to":[0,1,0,0]}', "out of range"),
        ('{"from":[0,0,0,-1],"to":[0,1,0,0]}', "out of range"),
        ('{"from":[0,true,0,0],"to":[0,1,0,0]}', "must be an integer"),
        (
            '{"from":[0,0,0,0],"to":[0,1,0,0],"extra":1}',
            "unexpected keys",
        ),
        (
            '{"from":[0,0,0,0],"to":[0,1,0,0],"promotion":"PAWN"}',
            "must be one of",
        ),
        (
            '{"from":[0,0,0,0],"to":[0,1,0,0],"promotion":"KING"}',
            "must be one of",
        ),
        (
            '{"from":[0,0,0,0],"to":[0,1,0,0],"is_castling":"yes"}',
            "must be a boolean",
        ),
    ],
)
def test_parse_json_move_invalid(bad: str, fragment: str) -> None:
    with pytest.raises(NotationError) as exc_info:
        parse_json_move(bad)
    assert fragment in str(exc_info.value), (
        f"expected fragment {fragment!r}, got {exc_info.value!s}"
    )


# Position round-trip -------------------------------------------------------


def test_position_round_trip_initial() -> None:
    gs = initial_position()
    js = render_json_position(gs)
    gs2 = parse_json_position(js)
    assert gs2.board == gs.board
    assert gs2.side_to_move is gs.side_to_move
    assert gs2.castling_rights == gs.castling_rights
    assert gs2.ep_target == gs.ep_target
    assert gs2.ep_victim == gs.ep_victim
    assert gs2.ep_axis == gs.ep_axis
    assert gs2.halfmove_clock == gs.halfmove_clock


def test_position_round_trip_empty_board() -> None:
    gs = GameState(board=Board4D(), side_to_move=Color.WHITE)
    js = render_json_position(gs)
    gs2 = parse_json_position(js)
    assert gs2.board == gs.board
    assert gs2.side_to_move is Color.WHITE
    assert gs2.castling_rights == frozenset()


def test_position_round_trip_all_piece_types() -> None:
    board = Board4D()
    placements = [
        (Square4D(0, 0, 0, 0), Piece(Color.WHITE, PieceType.ROOK)),
        (Square4D(1, 0, 0, 0), Piece(Color.WHITE, PieceType.KNIGHT)),
        (Square4D(2, 0, 0, 0), Piece(Color.WHITE, PieceType.BISHOP)),
        (Square4D(3, 0, 0, 0), Piece(Color.WHITE, PieceType.QUEEN)),
        (Square4D(4, 0, 0, 0), Piece(Color.WHITE, PieceType.KING)),
        (Square4D(5, 0, 0, 0), Piece(Color.WHITE, PieceType.PAWN, PawnAxis.Y)),
        (Square4D(6, 0, 0, 0), Piece(Color.WHITE, PieceType.PAWN, PawnAxis.W)),
        (Square4D(0, 7, 0, 0), Piece(Color.BLACK, PieceType.KING)),
        (Square4D(1, 7, 0, 0), Piece(Color.BLACK, PieceType.PAWN, PawnAxis.Y)),
        (Square4D(2, 7, 0, 0), Piece(Color.BLACK, PieceType.PAWN, PawnAxis.W)),
    ]
    for sq, p in placements:
        board.place(sq, p)
    gs = GameState(board=board, side_to_move=Color.BLACK, halfmove_clock=42)
    gs2 = parse_json_position(render_json_position(gs))
    assert gs2.board == board
    assert gs2.halfmove_clock == 42
    assert gs2.side_to_move is Color.BLACK


def test_position_round_trip_ep_state() -> None:
    board = Board4D()
    board.place(Square4D(4, 4, 3, 4), Piece(Color.BLACK, PieceType.PAWN, PawnAxis.W))
    gs = GameState(
        board=board,
        side_to_move=Color.WHITE,
        ep_target=Square4D(4, 4, 3, 5),
        ep_victim=Square4D(4, 4, 3, 4),
        ep_axis=PawnAxis.W,
    )
    gs2 = parse_json_position(render_json_position(gs))
    assert gs2.ep_target == gs.ep_target
    assert gs2.ep_victim == gs.ep_victim
    assert gs2.ep_axis is PawnAxis.W


def test_position_round_trip_castling_rights_subset() -> None:
    rights = frozenset(
        [
            (Color.WHITE, 0, 0, CastleSide.KINGSIDE),
            (Color.BLACK, 7, 7, CastleSide.QUEENSIDE),
        ]
    )
    gs = GameState(
        board=Board4D(), side_to_move=Color.WHITE, castling_rights=rights
    )
    gs2 = parse_json_position(render_json_position(gs))
    assert gs2.castling_rights == rights


def test_position_after_pawn_push_round_trips() -> None:
    gs = initial_position()
    gs.push(Move4D(Square4D(0, 1, 3, 3), Square4D(0, 3, 3, 3)))
    gs2 = parse_json_position(render_json_position(gs))
    assert gs2.board == gs.board
    assert gs2.side_to_move is gs.side_to_move
    assert gs2.ep_target == gs.ep_target
    assert gs2.ep_victim == gs.ep_victim
    assert gs2.ep_axis == gs.ep_axis


# Position invalid inputs ---------------------------------------------------


_VALID_MIN_POSITION = '{"placements":[],"side_to_move":"WHITE"}'


@pytest.mark.parametrize(
    ("bad", "fragment"),
    [
        ("not-json", "invalid JSON"),
        ('[]', "must be a JSON object"),
        ('{"side_to_move":"WHITE"}', "missing required key 'placements'"),
        ('{"placements":[]}', "missing required key 'side_to_move'"),
        (
            '{"placements":[],"side_to_move":"PURPLE"}',
            "must be one of",
        ),
        (
            '{"placements":"nope","side_to_move":"WHITE"}',
            "placements must be an array",
        ),
        (
            '{"placements":[{"square":[0,0,0,0],"color":"WHITE","piece_type":"ROOK","pawn_axis":null,"extra":1}],"side_to_move":"WHITE"}',
            "unexpected keys",
        ),
        (
            '{"placements":[{"square":[0,0,0,0],"color":"WHITE","piece_type":"PAWN","pawn_axis":null}],"side_to_move":"WHITE"}',
            "pawn_axis",
        ),
        (
            '{"placements":[{"square":[0,0,0,0],"color":"WHITE","piece_type":"ROOK","pawn_axis":"Y"}],"side_to_move":"WHITE"}',
            "pawn_axis",
        ),
        (
            '{"placements":[],"side_to_move":"WHITE","halfmove_clock":"3"}',
            "halfmove_clock must be an integer",
        ),
        (
            '{"placements":[],"side_to_move":"WHITE","halfmove_clock":-1}',
            "non-negative",
        ),
        (
            '{"placements":[],"side_to_move":"WHITE","ep_target":[0,0,0,0]}',
            "ep fields must be all null or all set",
        ),
        (
            '{"placements":[],"side_to_move":"WHITE","extra":1}',
            "unexpected keys",
        ),
        (
            '{"placements":[],"side_to_move":"WHITE","castling_rights":[{"color":"WHITE","slice":[0,0],"side":"UP"}]}',
            "must be one of",
        ),
        (
            '{"placements":[],"side_to_move":"WHITE","castling_rights":[{"color":"WHITE","slice":[0,0,0],"side":"KINGSIDE"}]}',
            "2-element array",
        ),
        (
            '{"placements":[],"side_to_move":"WHITE","castling_rights":[{"color":"WHITE","slice":[0,0],"side":"KINGSIDE"},{"color":"WHITE","slice":[0,0],"side":"KINGSIDE"}]}',
            "duplicates an earlier entry",
        ),
    ],
)
def test_parse_json_position_invalid(bad: str, fragment: str) -> None:
    with pytest.raises(NotationError) as exc_info:
        parse_json_position(bad)
    assert fragment in str(exc_info.value), (
        f"expected fragment {fragment!r}, got {exc_info.value!s}"
    )


def test_minimal_valid_position_parses() -> None:
    gs = parse_json_position(_VALID_MIN_POSITION)
    assert gs.board == Board4D()
    assert gs.halfmove_clock == 0
    assert gs.castling_rights == frozenset()


# Unicode and whitespace handling (stdlib json handles these for us) --------


def test_unicode_bom_parses_via_stdlib() -> None:
    # json.loads rejects a real BOM in the string, but accepts surrounding
    # ASCII whitespace including \t and \n.
    js = "\n\t" + _VALID_MIN_POSITION + "\n"
    gs = parse_json_position(js)
    assert gs.side_to_move is Color.WHITE


def test_placement_order_does_not_affect_parse() -> None:
    board = Board4D()
    board.place(Square4D(1, 0, 0, 0), Piece(Color.WHITE, PieceType.ROOK))
    board.place(Square4D(0, 0, 0, 0), Piece(Color.WHITE, PieceType.KNIGHT))
    gs = GameState(board=board, side_to_move=Color.WHITE)
    # Shuffled order in the JSON source; parser should not care.
    shuffled = (
        '{"placements":['
        '{"square":[1,0,0,0],"color":"WHITE","piece_type":"ROOK","pawn_axis":null},'
        '{"square":[0,0,0,0],"color":"WHITE","piece_type":"KNIGHT","pawn_axis":null}'
        '],"side_to_move":"WHITE"}'
    )
    gs2 = parse_json_position(shuffled)
    assert gs2.board == gs.board
