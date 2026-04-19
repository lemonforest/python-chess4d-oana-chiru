"""Phase 7D — game format (compact + JSON) and file I/O."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path

import pytest

from chess4d import (
    Board4D,
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
    parse_compact_game,
    parse_json_game,
    read_game_file,
    read_position_file,
    render_compact_game,
    render_json_game,
    write_game_file,
    write_position_file,
)
from chess4d.startpos import initial_position


# Fixtures -------------------------------------------------------------------


def _advance(start: GameState, moves: list[Move4D]) -> GameState:
    state = deepcopy(start)
    for m in moves:
        state.push(m)
    return state


def _pawn_push(from_sq: Square4D, to_sq: Square4D) -> Move4D:
    return Move4D(from_sq, to_sq)


def _two_pawn_game() -> tuple[GameState, list[Move4D]]:
    """A 2-ply fixture: white then black Y-pawn double pushes."""
    start = initial_position()
    moves = [
        _pawn_push(Square4D(0, 1, 3, 3), Square4D(0, 3, 3, 3)),
        _pawn_push(Square4D(0, 6, 3, 3), Square4D(0, 4, 3, 3)),
    ]
    return start, moves


def _longer_game() -> tuple[GameState, list[Move4D]]:
    """An 8-ply alternating pawn-push game across slice (3, 3).

    Only even-``x`` files are exercised because those pawns are
    Y-oriented (paper §3.3); odd-``x`` pawns are W-oriented and
    advance along a different axis. Restricting to Y-pawns keeps the
    fixture purely about the notation layer, not pawn-axis mechanics.
    """
    start = initial_position()
    moves: list[Move4D] = []
    # White pushes pawns from (x, 1, 3, 3) to (x, 2, 3, 3), alternating
    # with black pushes from (x, 6, 3, 3) to (x, 5, 3, 3).
    for x in (0, 2, 4, 6):
        moves.append(_pawn_push(Square4D(x, 1, 3, 3), Square4D(x, 2, 3, 3)))
        moves.append(_pawn_push(Square4D(x, 6, 3, 3), Square4D(x, 5, 3, 3)))
    return start, moves


# ---------------------------------------------------------------------------
# Compact game format
# ---------------------------------------------------------------------------


def test_compact_game_initial_start_round_trip() -> None:
    start, moves = _two_pawn_game()
    s = render_compact_game(start, moves)
    start2, moves2 = parse_compact_game(s)
    assert start2.board == start.board
    assert start2.side_to_move is start.side_to_move
    assert moves2 == moves


def test_compact_game_omits_start_when_equal_to_initial() -> None:
    start, moves = _two_pawn_game()
    s = render_compact_game(start, moves)
    # The emitted text should NOT contain a position header like "w - ... 0".
    assert not any(
        line.strip().startswith(("w ", "b "))
        and len(line.strip().split()) == 4
        for line in s.splitlines()
    )


def test_compact_game_force_start_includes_position() -> None:
    start, moves = _two_pawn_game()
    s = render_compact_game(start, moves, force_start=True)
    # First non-empty line should be a position header.
    first = next(line for line in s.splitlines() if line.strip())
    parts = first.strip().split()
    assert len(parts) == 4 and parts[0] in ("w", "b")


def test_compact_game_custom_start_round_trip() -> None:
    board = Board4D()
    board.place(Square4D(4, 0, 0, 0), Piece(Color.WHITE, PieceType.KING))
    board.place(Square4D(4, 7, 0, 0), Piece(Color.BLACK, PieceType.KING))
    start = GameState(board=board, side_to_move=Color.WHITE)
    moves = [Move4D(Square4D(4, 0, 0, 0), Square4D(4, 1, 0, 0))]
    s = render_compact_game(start, moves)
    start2, moves2 = parse_compact_game(s)
    assert start2.board == start.board
    assert start2.side_to_move is Color.WHITE
    assert moves2 == moves


def test_compact_game_empty_string_yields_initial_with_no_moves() -> None:
    start, moves = parse_compact_game("")
    assert start.board == initial_position().board
    assert moves == []


def test_compact_game_comments_and_blanks_are_ignored() -> None:
    raw = "\n".join(
        [
            "# a comment line",
            "# another",
            "",
            "a2c4-a4c4",
            "  ",
            "# trailing comment",
            "a7c4-a5c4",
        ]
    )
    start, moves = parse_compact_game(raw)
    assert start.board == initial_position().board
    assert len(moves) == 2
    assert moves[0].from_sq == Square4D(0, 1, 2, 3)


def test_compact_game_capture_marker_replays_correctly() -> None:
    # Build a game where move 1 captures.
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), Piece(Color.WHITE, PieceType.KING))
    board.place(Square4D(7, 7, 0, 0), Piece(Color.BLACK, PieceType.KING))
    board.place(Square4D(3, 3, 0, 0), Piece(Color.WHITE, PieceType.ROOK))
    board.place(Square4D(3, 5, 0, 0), Piece(Color.BLACK, PieceType.PAWN, PawnAxis.Y))
    start = GameState(board=board, side_to_move=Color.WHITE)
    moves = [Move4D(Square4D(3, 3, 0, 0), Square4D(3, 5, 0, 0))]
    s = render_compact_game(start, moves)
    # The capture line should use 'x' as the separator.
    assert "d4a1xd6a1" in s
    start2, moves2 = parse_compact_game(s)
    assert moves2 == moves


def test_compact_game_trailing_newline_in_output() -> None:
    start, moves = _two_pawn_game()
    s = render_compact_game(start, moves)
    assert s.endswith("\n")


def test_compact_game_bad_move_reports_index() -> None:
    raw = "a2c4-a4c4\nxxxxxxxxx"
    with pytest.raises(NotationError) as exc_info:
        parse_compact_game(raw)
    assert "move #2" in str(exc_info.value)


def test_compact_game_longer_replay_matches_end_state() -> None:
    start, moves = _longer_game()
    s = render_compact_game(start, moves)
    start2, moves2 = parse_compact_game(s)
    assert moves2 == moves
    final = _advance(start, moves)
    final2 = _advance(start2, moves2)
    assert final.board == final2.board
    assert final.side_to_move is final2.side_to_move
    assert final.halfmove_clock == final2.halfmove_clock


# ---------------------------------------------------------------------------
# JSON game format
# ---------------------------------------------------------------------------


def test_json_game_initial_start_round_trip() -> None:
    start, moves = _two_pawn_game()
    s = render_json_game(start, moves)
    obj = json.loads(s)
    assert obj["start"] is None
    assert len(obj["moves"]) == 2
    start2, moves2 = parse_json_game(s)
    assert start2.board == start.board
    assert moves2 == moves


def test_json_game_custom_start_round_trip() -> None:
    board = Board4D()
    board.place(Square4D(4, 0, 0, 0), Piece(Color.WHITE, PieceType.KING))
    board.place(Square4D(4, 7, 0, 0), Piece(Color.BLACK, PieceType.KING))
    start = GameState(board=board, side_to_move=Color.WHITE)
    moves = [Move4D(Square4D(4, 0, 0, 0), Square4D(4, 1, 0, 0))]
    s = render_json_game(start, moves)
    obj = json.loads(s)
    assert obj["start"] is not None
    start2, moves2 = parse_json_game(s)
    assert start2.board == start.board
    assert moves2 == moves


def test_json_game_force_start_emits_initial_position() -> None:
    start, moves = _two_pawn_game()
    s = render_json_game(start, moves, force_start=True)
    obj = json.loads(s)
    assert obj["start"] is not None
    assert isinstance(obj["start"]["placements"], list)


def test_json_game_indent_produces_multiline_output() -> None:
    start, moves = _two_pawn_game()
    one_line = render_json_game(start, moves)
    pretty = render_json_game(start, moves, indent=2)
    assert "\n" not in one_line
    assert "\n" in pretty


def test_json_game_null_start_yields_initial_position() -> None:
    s = '{"start":null,"moves":[]}'
    start, moves = parse_json_game(s)
    assert start.board == initial_position().board
    assert moves == []


def test_json_game_empty_moves_array() -> None:
    s = '{"start":null,"moves":[]}'
    _, moves = parse_json_game(s)
    assert moves == []


def test_json_game_roundtrip_longer_game() -> None:
    start, moves = _longer_game()
    s = render_json_game(start, moves)
    start2, moves2 = parse_json_game(s)
    assert moves2 == moves
    final = _advance(start, moves)
    final2 = _advance(start2, moves2)
    assert final.board == final2.board


@pytest.mark.parametrize(
    ("bad", "fragment"),
    [
        ("[]", "must be a JSON object"),
        ('"nope"', "must be a JSON object"),
        ('{"moves":[], "extra":1}', "unexpected keys"),
        ('{"start":null}', "missing required key 'moves'"),
        ('{"start":null,"moves":"not-an-array"}', "must be an array"),
        ('{"start":null,"moves":[{"from":[0,0,0,0]}]}', "missing required key 'to'"),
        ("{not-json", "invalid JSON"),
    ],
)
def test_json_game_invalid_raises(bad: str, fragment: str) -> None:
    with pytest.raises(NotationError) as exc_info:
        parse_json_game(bad)
    assert fragment in str(exc_info.value)


# ---------------------------------------------------------------------------
# File I/O
# ---------------------------------------------------------------------------


def test_write_and_read_game_file_compact(tmp_path: Path) -> None:
    start, moves = _two_pawn_game()
    p = tmp_path / "game.c4d"
    write_game_file(p, start, moves)
    assert p.exists()
    start2, moves2 = read_game_file(p)
    assert moves2 == moves
    assert start2.board == start.board


def test_write_and_read_game_file_json(tmp_path: Path) -> None:
    start, moves = _two_pawn_game()
    p = tmp_path / "game.json"
    write_game_file(p, start, moves)
    # File should be pretty-printed (contain newlines).
    text = p.read_text(encoding="utf-8")
    assert "\n" in text
    start2, moves2 = read_game_file(p)
    assert moves2 == moves
    assert start2.board == start.board


def test_write_and_read_position_file_compact(tmp_path: Path) -> None:
    gs = initial_position()
    p = tmp_path / "pos.c4dpos"
    write_position_file(p, gs)
    gs2 = read_position_file(p)
    assert gs2.board == gs.board


def test_write_and_read_position_file_json(tmp_path: Path) -> None:
    gs = initial_position()
    p = tmp_path / "pos.json"
    write_position_file(p, gs)
    gs2 = read_position_file(p)
    assert gs2.board == gs.board


def test_file_format_override_ignores_extension(tmp_path: Path) -> None:
    start, moves = _two_pawn_game()
    p = tmp_path / "game.json"  # json extension but we force compact
    write_game_file(p, start, moves, format="compact")
    # The content is compact, even though the extension is .json.
    text = p.read_text(encoding="utf-8")
    assert not text.lstrip().startswith("{")
    start2, moves2 = read_game_file(p, format="compact")
    assert moves2 == moves


def test_file_unknown_extension_raises(tmp_path: Path) -> None:
    p = tmp_path / "game.txt"
    with pytest.raises(NotationError) as exc_info:
        read_game_file(p)
    assert "cannot infer notation format" in str(exc_info.value)


def test_file_unknown_extension_write_raises(tmp_path: Path) -> None:
    start, moves = _two_pawn_game()
    p = tmp_path / "game.txt"
    with pytest.raises(NotationError):
        write_game_file(p, start, moves)


def test_file_explicit_format_validates(tmp_path: Path) -> None:
    start, moves = _two_pawn_game()
    p = tmp_path / "game.c4d"
    with pytest.raises(NotationError) as exc_info:
        write_game_file(p, start, moves, format="bogus")  # type: ignore[arg-type]
    assert "must be 'compact' or 'json'" in str(exc_info.value)


def test_file_custom_start_replays_identically(tmp_path: Path) -> None:
    board = Board4D()
    board.place(Square4D(4, 0, 0, 0), Piece(Color.WHITE, PieceType.KING))
    board.place(Square4D(4, 7, 0, 0), Piece(Color.BLACK, PieceType.KING))
    board.place(
        Square4D(2, 1, 0, 0), Piece(Color.WHITE, PieceType.PAWN, PawnAxis.Y)
    )
    start = GameState(
        board=board,
        side_to_move=Color.WHITE,
        castling_rights=frozenset(),
    )
    moves = [Move4D(Square4D(2, 1, 0, 0), Square4D(2, 3, 0, 0))]

    for ext in (".c4d", ".json"):
        p = tmp_path / f"game{ext}"
        write_game_file(p, start, moves)
        start2, moves2 = read_game_file(p)
        assert moves2 == moves
        assert start2.board == start.board

        replayed = _advance(start, moves)
        replayed2 = _advance(start2, moves2)
        assert replayed.board == replayed2.board


def test_file_long_game_round_trip(tmp_path: Path) -> None:
    """A 32-ply game's moves and end-state match across write/read.

    Moves are pawn double-pushes on the four central ``(z, w)``-slices —
    the only slices that carry both colors, so black has pieces to move
    in response. Only even-``x`` files are pushed because those pawns
    are Y-oriented (paper §3.3); the odd-``x`` pawns are W-oriented
    and advance along a different axis.
    """
    start = initial_position()
    state = deepcopy(start)
    moves: list[Move4D] = []
    slices = [(3, 3), (3, 4), (4, 3), (4, 4)]
    for z, w in slices:
        for x in (0, 2, 4, 6):
            white = Move4D(Square4D(x, 1, z, w), Square4D(x, 3, z, w))
            moves.append(white)
            state.push(white)
            black = Move4D(Square4D(x, 6, z, w), Square4D(x, 4, z, w))
            moves.append(black)
            state.push(black)
    assert len(moves) == 32

    for ext in (".c4d", ".json"):
        p = tmp_path / f"long{ext}"
        write_game_file(p, start, moves)
        start2, moves2 = read_game_file(p)
        assert moves2 == moves
        end = _advance(start2, moves2)
        assert end.board == state.board
        assert end.side_to_move is state.side_to_move
        assert end.halfmove_clock == state.halfmove_clock


def test_file_force_start_emits_header(tmp_path: Path) -> None:
    start, moves = _two_pawn_game()
    p = tmp_path / "game.c4d"
    write_game_file(p, start, moves, force_start=True)
    text = p.read_text(encoding="utf-8")
    # First line should be a position header.
    first_line = text.splitlines()[0]
    assert first_line.startswith("w ")


def test_file_accepts_str_path(tmp_path: Path) -> None:
    start, moves = _two_pawn_game()
    p = str(tmp_path / "game.c4d")
    write_game_file(p, start, moves)
    start2, moves2 = read_game_file(p)
    assert moves2 == moves


def test_file_uppercase_extension_is_recognized(tmp_path: Path) -> None:
    start, moves = _two_pawn_game()
    p = tmp_path / "GAME.C4D"
    write_game_file(p, start, moves)
    start2, moves2 = read_game_file(p)
    assert moves2 == moves


def test_file_malformed_content_reports_clearly(tmp_path: Path) -> None:
    # A file with the right extension but garbage content.
    p = tmp_path / "broken.json"
    p.write_text('{"start": null, "moves":', encoding="utf-8")
    with pytest.raises(NotationError) as exc_info:
        read_game_file(p)
    assert "invalid JSON" in str(exc_info.value)


def test_file_malformed_compact_move_points_to_line(tmp_path: Path) -> None:
    start, moves = _two_pawn_game()
    p = tmp_path / "broken.c4d"
    # Write the legit moves, then corrupt the last line.
    text = render_compact_game(start, moves)
    text += "garbage-line\n"
    p.write_text(text, encoding="utf-8")
    with pytest.raises(NotationError) as exc_info:
        read_game_file(p)
    # The error should mention a move index > 0.
    assert "move #" in str(exc_info.value)
