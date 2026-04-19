"""Phase 7E — top-level auto-detect notation API."""

from __future__ import annotations

import pytest

from chess4d import Move4D, Square4D
from chess4d.notation import (
    NotationError,
    parse_game,
    parse_move,
    parse_position,
    render_game,
    render_move,
    render_position,
)
from chess4d.startpos import initial_position


# parse_move -----------------------------------------------------------------


def test_parse_move_detects_compact() -> None:
    m = parse_move("a1c4-a3c4")
    assert m == Move4D(Square4D(0, 0, 2, 3), Square4D(0, 2, 2, 3))


def test_parse_move_detects_json() -> None:
    s = '{"from":[0,0,2,3],"to":[0,2,2,3]}'
    m = parse_move(s)
    assert m == Move4D(Square4D(0, 0, 2, 3), Square4D(0, 2, 2, 3))


def test_parse_move_detects_json_after_leading_whitespace() -> None:
    s = '   \n\t {"from":[0,0,2,3],"to":[0,2,2,3]}'
    m = parse_move(s)
    assert m.from_sq == Square4D(0, 0, 2, 3)


def test_parse_move_explicit_format_overrides_detection() -> None:
    # A string starting with '{' but with format="compact" should be
    # routed to the compact parser (which will reject it).
    with pytest.raises(NotationError):
        parse_move('{"from":[0,0,0,0]}', format="compact")


def test_parse_move_invalid_format_raises() -> None:
    with pytest.raises(NotationError) as exc_info:
        parse_move("a1c4-a3c4", format="yaml")  # type: ignore[arg-type]
    assert "must be 'compact' or 'json'" in str(exc_info.value)


# render_move ----------------------------------------------------------------


def test_render_move_defaults_to_compact() -> None:
    m = Move4D(Square4D(0, 0, 2, 3), Square4D(0, 2, 2, 3))
    assert render_move(m) == "a1c4-a3c4"


def test_render_move_json() -> None:
    m = Move4D(Square4D(0, 0, 2, 3), Square4D(0, 2, 2, 3))
    s = render_move(m, format="json")
    assert s.startswith("{")
    assert '"from":[0,0,2,3]' in s


def test_render_move_capture_flag_passes_through_compact() -> None:
    m = Move4D(Square4D(0, 0, 2, 3), Square4D(0, 2, 2, 3))
    assert render_move(m, is_capture=True) == "a1c4xa3c4"


def test_render_move_capture_flag_ignored_for_json() -> None:
    m = Move4D(Square4D(0, 0, 2, 3), Square4D(0, 2, 2, 3))
    # is_capture has no effect on JSON output.
    s1 = render_move(m, format="json", is_capture=False)
    s2 = render_move(m, format="json", is_capture=True)
    assert s1 == s2


# parse_position / render_position -------------------------------------------


def test_parse_position_detects_compact() -> None:
    gs = parse_position("w - - 0")
    assert gs.side_to_move.name == "WHITE"


def test_parse_position_detects_json() -> None:
    gs = parse_position('{"placements":[],"side_to_move":"WHITE"}')
    assert gs.side_to_move.name == "WHITE"


def test_render_position_round_trip_compact() -> None:
    gs = initial_position()
    s = render_position(gs)  # default compact
    gs2 = parse_position(s)
    assert gs2.board == gs.board


def test_render_position_round_trip_json() -> None:
    gs = initial_position()
    s = render_position(gs, format="json")
    assert s.startswith("{")
    gs2 = parse_position(s)
    assert gs2.board == gs.board


# parse_game / render_game ---------------------------------------------------


def test_parse_game_detects_compact() -> None:
    start, moves = parse_game("a2c4-a4c4")
    assert start.board == initial_position().board
    assert len(moves) == 1


def test_parse_game_detects_json() -> None:
    s = (
        '{"start":null,"moves":[{"from":[0,1,2,3],"to":[0,3,2,3],'
        '"promotion":null,"is_castling":false,"is_en_passant":false}]}'
    )
    start, moves = parse_game(s)
    assert len(moves) == 1
    assert moves[0].from_sq == Square4D(0, 1, 2, 3)


def test_render_game_round_trip_both_formats() -> None:
    start = initial_position()
    moves = [Move4D(Square4D(0, 1, 3, 3), Square4D(0, 3, 3, 3))]
    for fmt in ("compact", "json"):
        s = render_game(start, moves, format=fmt)  # type: ignore[arg-type]
        start2, moves2 = parse_game(s)
        assert moves2 == moves
        assert start2.board == start.board


def test_render_game_force_start_both_formats() -> None:
    start = initial_position()
    moves = [Move4D(Square4D(0, 1, 3, 3), Square4D(0, 3, 3, 3))]
    compact_forced = render_game(start, moves, format="compact", force_start=True)
    json_forced = render_game(start, moves, format="json", force_start=True)
    # Compact: first line is position header.
    assert compact_forced.splitlines()[0].startswith("w ")
    # JSON: "start" is not null.
    assert '"start":null' not in json_forced


def test_parse_game_empty_string_is_compact() -> None:
    # Empty string detection falls back to compact; compact treats it
    # as an empty game (initial_position, no moves).
    start, moves = parse_game("")
    assert start.board == initial_position().board
    assert moves == []


def test_parse_move_whitespace_only_compact_raises() -> None:
    # All-whitespace routes to compact, which rejects empty moves.
    with pytest.raises(NotationError):
        parse_move("   ")


# Explicit format= on parse_* overrides detection ----------------------------


def test_parse_position_explicit_compact_on_json_input_raises() -> None:
    s = '{"placements":[],"side_to_move":"WHITE"}'
    with pytest.raises(NotationError):
        parse_position(s, format="compact")


def test_parse_game_explicit_json_on_compact_input_raises() -> None:
    with pytest.raises(NotationError):
        parse_game("a2c4-a4c4", format="json")


# Mixed-format in one session ------------------------------------------------


def test_same_move_in_both_formats_parses_to_equal_move4d() -> None:
    compact_m = parse_move("a1c4-a3c4")
    json_m = parse_move('{"from":[0,0,2,3],"to":[0,2,2,3]}')
    assert compact_m == json_m


def test_same_position_in_both_formats_parses_to_equal_gamestate() -> None:
    gs = initial_position()
    compact_s = render_position(gs)
    json_s = render_position(gs, format="json")
    gs_from_compact = parse_position(compact_s)
    gs_from_json = parse_position(json_s)
    assert gs_from_compact.board == gs_from_json.board
    assert gs_from_compact.side_to_move is gs_from_json.side_to_move
