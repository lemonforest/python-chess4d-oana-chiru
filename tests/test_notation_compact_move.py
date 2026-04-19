"""Phase 7A — compact move notation parse/render/round-trip."""

from __future__ import annotations

import pytest
from hypothesis import given, strategies as st

from chess4d import (
    BOARD_SIZE,
    CastleSide,
    Color,
    Move4D,
    PieceType,
    Square4D,
)
from chess4d.notation import (
    NotationError,
    parse_compact_move,
    render_compact_move,
)

# Reusable strategies ---------------------------------------------------------

_coord = st.integers(min_value=0, max_value=BOARD_SIZE - 1)
_sq = st.builds(Square4D, _coord, _coord, _coord, _coord)
_promo = st.sampled_from(
    [PieceType.QUEEN, PieceType.ROOK, PieceType.BISHOP, PieceType.KNIGHT]
)

# Ordinary moves --------------------------------------------------------------


def test_parse_ordinary_spec_example() -> None:
    # Spec sample: a1c4-a2c4  (x=0, y=0, z=2, w=3) -> (x=0, y=1, z=2, w=3)
    m = parse_compact_move("a1c4-a2c4")
    assert m == Move4D(Square4D(0, 0, 2, 3), Square4D(0, 1, 2, 3))
    assert m.promotion is None
    assert not m.is_castling
    assert not m.is_en_passant


def test_parse_ordinary_corner_to_corner() -> None:
    m = parse_compact_move("h8h8-a1a1")
    assert m.from_sq == Square4D(7, 7, 7, 7)
    assert m.to_sq == Square4D(0, 0, 0, 0)


def test_render_ordinary_matches_spec_example() -> None:
    m = Move4D(Square4D(0, 0, 2, 3), Square4D(0, 1, 2, 3))
    assert render_compact_move(m) == "a1c4-a2c4"


# Captures --------------------------------------------------------------------


def test_parse_capture_spec_example() -> None:
    m = parse_compact_move("a1c4xa3c4")
    assert m == Move4D(Square4D(0, 0, 2, 3), Square4D(0, 2, 2, 3))


def test_render_capture_requires_flag() -> None:
    m = Move4D(Square4D(0, 0, 2, 3), Square4D(0, 2, 2, 3))
    assert render_compact_move(m, is_capture=True) == "a1c4xa3c4"
    # Default is non-capture regardless of actual board state.
    assert render_compact_move(m) == "a1c4-a3c4"


# Promotion -------------------------------------------------------------------


@pytest.mark.parametrize(
    ("ch", "pt"),
    [
        ("Q", PieceType.QUEEN),
        ("R", PieceType.ROOK),
        ("B", PieceType.BISHOP),
        ("N", PieceType.KNIGHT),
    ],
)
def test_parse_promotion_each_type(ch: str, pt: PieceType) -> None:
    m = parse_compact_move(f"a7c4-a8c4={ch}")
    assert m.promotion is pt
    assert m.from_sq == Square4D(0, 6, 2, 3)
    assert m.to_sq == Square4D(0, 7, 2, 3)


def test_parse_capture_promotion_spec_example() -> None:
    # Spec sample: a2c4xb3c4=Q
    m = parse_compact_move("a2c4xb3c4=Q")
    assert m.promotion is PieceType.QUEEN


def test_render_promotion_non_capture() -> None:
    m = Move4D(Square4D(0, 6, 2, 3), Square4D(0, 7, 2, 3), promotion=PieceType.QUEEN)
    assert render_compact_move(m) == "a7c4-a8c4=Q"


def test_render_promotion_with_capture_flag() -> None:
    m = Move4D(Square4D(0, 6, 2, 3), Square4D(1, 7, 2, 3), promotion=PieceType.KNIGHT)
    assert render_compact_move(m, is_capture=True) == "a7c4xb8c4=N"


# En passant ------------------------------------------------------------------


def test_parse_ep_spec_example() -> None:
    # Spec sample: a2c4xa3c4ep
    m = parse_compact_move("a2c4xa3c4ep")
    assert m.is_en_passant
    assert m.from_sq == Square4D(0, 1, 2, 3)
    assert m.to_sq == Square4D(0, 2, 2, 3)


def test_render_ep_uses_x_and_suffix() -> None:
    m = Move4D(Square4D(0, 1, 2, 3), Square4D(0, 2, 2, 3), is_en_passant=True)
    # Renderer forces 'x' for ep regardless of the flag.
    assert render_compact_move(m) == "a2c4xa3c4ep"
    assert render_compact_move(m, is_capture=True) == "a2c4xa3c4ep"


# Castling --------------------------------------------------------------------


def test_parse_castle_white_kingside() -> None:
    # Spec: O-O@c4 is kingside on slice z=2, w=3.
    m = parse_compact_move("O-O@c4")
    assert m == Move4D(
        Square4D(4, 0, 2, 3),
        Square4D(6, 0, 2, 3),
        is_castling=True,
    )


def test_parse_castle_white_queenside() -> None:
    m = parse_compact_move("O-O-O@c4")
    assert m == Move4D(
        Square4D(4, 0, 2, 3),
        Square4D(2, 0, 2, 3),
        is_castling=True,
    )


def test_parse_castle_black_kingside() -> None:
    m = parse_compact_move("o-o@c4")
    assert m == Move4D(
        Square4D(4, 7, 2, 3),
        Square4D(6, 7, 2, 3),
        is_castling=True,
    )


def test_parse_castle_black_queenside() -> None:
    m = parse_compact_move("o-o-o@c4")
    assert m == Move4D(
        Square4D(4, 7, 2, 3),
        Square4D(2, 7, 2, 3),
        is_castling=True,
    )


def test_render_castle_white_kingside() -> None:
    m = Move4D(Square4D(4, 0, 2, 3), Square4D(6, 0, 2, 3), is_castling=True)
    assert render_compact_move(m) == "O-O@c4"


def test_render_castle_white_queenside() -> None:
    m = Move4D(Square4D(4, 0, 2, 3), Square4D(2, 0, 2, 3), is_castling=True)
    assert render_compact_move(m) == "O-O-O@c4"


def test_render_castle_black_kingside() -> None:
    m = Move4D(Square4D(4, 7, 2, 3), Square4D(6, 7, 2, 3), is_castling=True)
    assert render_compact_move(m) == "o-o@c4"


def test_render_castle_black_queenside() -> None:
    m = Move4D(Square4D(4, 7, 2, 3), Square4D(2, 7, 2, 3), is_castling=True)
    assert render_compact_move(m) == "o-o-o@c4"


# Invalid inputs --------------------------------------------------------------


@pytest.mark.parametrize(
    ("bad", "fragment"),
    [
        ("", "empty move"),
        ("a1c", "too short"),
        ("z1c4-a2c4", "letter a-h"),
        ("a9c4-a2c4", "digit 1-8"),
        ("1aa1-a2c4", "letter a-h"),
        ("a1c4!a2c4", "'-' or 'x'"),
        ("a1c4-a2c4=q", "Q/R/B/N"),
        ("a1c4-a2c4=X", "Q/R/B/N"),
        ("a1c4-a2c4=", "trailing"),
        ("a1c4-a2c4ep", "requires 'x'"),
        ("a1c4-a2c4junk", "trailing"),
        ("O-O", "@<slice>"),
        ("O-O@c", "2 characters"),
        ("O-Ox@c4", "invalid castling token"),
        ("O-O-O-O@c4", "invalid castling token"),
        ("O-O@i4", "letter a-h"),
        ("O-O@c9", "digit 1-8"),
    ],
)
def test_parse_invalid_raises(bad: str, fragment: str) -> None:
    with pytest.raises(NotationError) as exc_info:
        parse_compact_move(bad)
    assert fragment in str(exc_info.value), (
        f"expected fragment {fragment!r} in error, got {exc_info.value!s}"
    )


def test_notation_error_is_valueerror() -> None:
    with pytest.raises(ValueError):
        parse_compact_move("")


# Render rejects malformed castling -------------------------------------------


def test_render_castle_rejects_non_back_rank() -> None:
    m = Move4D(Square4D(4, 3, 2, 3), Square4D(6, 3, 2, 3), is_castling=True)
    with pytest.raises(ValueError):
        render_compact_move(m)


def test_render_castle_rejects_bad_king_x() -> None:
    m = Move4D(Square4D(3, 0, 2, 3), Square4D(6, 0, 2, 3), is_castling=True)
    with pytest.raises(ValueError):
        render_compact_move(m)


def test_render_castle_rejects_slice_change() -> None:
    m = Move4D(Square4D(4, 0, 2, 3), Square4D(6, 0, 3, 3), is_castling=True)
    with pytest.raises(ValueError):
        render_compact_move(m)


# Round-trip (Hypothesis) -----------------------------------------------------


@given(from_sq=_sq, to_sq=_sq)
def test_roundtrip_ordinary(from_sq: Square4D, to_sq: Square4D) -> None:
    m = Move4D(from_sq, to_sq)
    assert parse_compact_move(render_compact_move(m)) == m


@given(from_sq=_sq, to_sq=_sq)
def test_roundtrip_capture(from_sq: Square4D, to_sq: Square4D) -> None:
    m = Move4D(from_sq, to_sq)
    s = render_compact_move(m, is_capture=True)
    # Capture marker is informational; parsed Move4D compares equal.
    assert parse_compact_move(s) == m


@given(from_sq=_sq, to_sq=_sq, promo=_promo)
def test_roundtrip_promotion(
    from_sq: Square4D, to_sq: Square4D, promo: PieceType
) -> None:
    m = Move4D(from_sq, to_sq, promotion=promo)
    assert parse_compact_move(render_compact_move(m)) == m
    assert parse_compact_move(render_compact_move(m, is_capture=True)) == m


@given(from_sq=_sq, to_sq=_sq)
def test_roundtrip_en_passant(from_sq: Square4D, to_sq: Square4D) -> None:
    m = Move4D(from_sq, to_sq, is_en_passant=True)
    assert parse_compact_move(render_compact_move(m)) == m


@given(
    color=st.sampled_from([Color.WHITE, Color.BLACK]),
    side=st.sampled_from([CastleSide.KINGSIDE, CastleSide.QUEENSIDE]),
    z=_coord,
    w=_coord,
)
def test_roundtrip_castle(
    color: Color, side: CastleSide, z: int, w: int
) -> None:
    back_y = 0 if color is Color.WHITE else BOARD_SIZE - 1
    to_x = 6 if side is CastleSide.KINGSIDE else 2
    m = Move4D(
        Square4D(4, back_y, z, w),
        Square4D(to_x, back_y, z, w),
        is_castling=True,
    )
    assert parse_compact_move(render_compact_move(m)) == m
