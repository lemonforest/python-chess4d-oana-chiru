"""chess4d notation layer (Phase 7).

Serialization formats for moves, positions, and games:

* :mod:`chess4d.notation.compact` — human-readable coordinate notation
  (Format A). Designed to be eyeballable like a chess scoresheet while
  being honest about 4D coordinates.
* :mod:`chess4d.notation.json_format` — machine-readable JSON for
  tooling and interchange (Format B).

Neither Oana & Chiru nor any other published 4D-chess implementation
ships a notation format; these are the reference formats for Python
tooling around the chess4d package.

Public API
----------
Format-specific parse/render helpers live in the two submodules
(``parse_compact_move``/``render_compact_move``, ``parse_json_move``/
``render_json_move``, plus ``_position`` and ``_game`` variants).

File I/O lives here on the package root:

* :func:`read_game_file` / :func:`write_game_file` — games on disk.
* :func:`read_position_file` / :func:`write_position_file` —
  standalone positions on disk.

File format is inferred from extension:

* ``.c4d`` — compact game
* ``.c4dpos`` — compact position
* ``.json`` — JSON game or JSON position (parser tells the two apart
  from the object's top-level keys: ``{"moves": ...}`` is a game,
  ``{"placements": ...}`` is a position).

Pass an explicit ``format="compact"`` or ``format="json"`` to override
extension-based inference.

All parsers raise :class:`NotationError` (a :class:`ValueError`
subclass) for syntactic failures. Semantic validation — "is this a
legal move in the current state" — is not the notation layer's job;
that lives on :meth:`chess4d.GameState.push`.
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

from chess4d.notation.compact import (
    parse_compact_game,
    parse_compact_move,
    parse_compact_position,
    render_compact_game,
    render_compact_move,
    render_compact_position,
)
from chess4d.notation.errors import NotationError
from chess4d.notation.json_format import (
    parse_json_game,
    parse_json_move,
    parse_json_position,
    render_json_game,
    render_json_move,
    render_json_position,
)
from chess4d.state import GameState
from chess4d.types import Move4D

_Format = Literal["compact", "json"]


_EXT_FORMAT: dict[str, tuple[_Format, str]] = {
    ".c4d": ("compact", "game"),
    ".c4dpos": ("compact", "position"),
    ".json": ("json", "either"),
}


def _detect_format(s: str) -> _Format:
    """Infer the format from a serialized string's leading character.

    A string whose first non-whitespace character is ``{`` is JSON;
    anything else is compact. JSON strings starting with ``[`` or a
    scalar are rejected by the underlying parser (notation payloads are
    always objects), so this heuristic is safe.
    """
    for ch in s:
        if ch.isspace():
            continue
        return "json" if ch == "{" else "compact"
    # All-whitespace input: defer to compact, whose parser will raise
    # a specific "no header / empty move" error.
    return "compact"


def _validate_format(format: _Format) -> None:
    if format not in ("compact", "json"):
        raise NotationError(
            f"format must be 'compact' or 'json', got {format!r}"
        )


def _format_from_path(path: Path) -> _Format:
    """Infer ``"compact"`` or ``"json"`` from a file path's extension.

    Raises :class:`NotationError` if the extension is not one of the
    three recognized suffixes.
    """
    suffix = path.suffix.lower()
    if suffix not in _EXT_FORMAT:
        raise NotationError(
            f"cannot infer notation format from extension {suffix!r}; "
            f"expected one of {sorted(_EXT_FORMAT)!r} or pass an explicit "
            "format= argument"
        )
    return _EXT_FORMAT[suffix][0]


def _resolve_format(path: Path, format: _Format | None) -> _Format:
    if format is not None:
        _validate_format(format)
        return format
    return _format_from_path(path)


# Top-level auto-detect API (Phase 7E) --------------------------------------


def parse_move(s: str, *, format: _Format | None = None) -> Move4D:
    """Parse a move string. Auto-detects compact vs JSON if ``format`` is None.

    Detection uses the first non-whitespace character: ``{`` selects
    JSON, anything else selects compact. Pass ``format=`` to skip
    detection.
    """
    if format is None:
        format = _detect_format(s)
    else:
        _validate_format(format)
    if format == "json":
        return parse_json_move(s)
    return parse_compact_move(s)


def render_move(
    m: Move4D,
    *,
    format: _Format = "compact",
    is_capture: bool = False,
) -> str:
    """Render a move to the chosen format (default compact).

    ``is_capture`` only affects the compact format — it selects the
    ``x`` separator for ordinary capturing moves. JSON carries no
    capture marker so the flag is ignored there.
    """
    _validate_format(format)
    if format == "json":
        return render_json_move(m)
    return render_compact_move(m, is_capture=is_capture)


def parse_position(s: str, *, format: _Format | None = None) -> GameState:
    """Parse a position string. Auto-detects compact vs JSON if ``format`` is None."""
    if format is None:
        format = _detect_format(s)
    else:
        _validate_format(format)
    if format == "json":
        return parse_json_position(s)
    return parse_compact_position(s)


def render_position(gs: GameState, *, format: _Format = "compact") -> str:
    """Render a position to the chosen format (default compact)."""
    _validate_format(format)
    if format == "json":
        return render_json_position(gs)
    return render_compact_position(gs)


def parse_game(
    s: str, *, format: _Format | None = None
) -> tuple[GameState, list[Move4D]]:
    """Parse a game string. Auto-detects compact vs JSON if ``format`` is None.

    Returns ``(start_state, move_list)`` — the caller is responsible
    for replaying the moves onto ``start_state`` to reach the end
    position.
    """
    if format is None:
        format = _detect_format(s)
    else:
        _validate_format(format)
    if format == "json":
        return parse_json_game(s)
    return parse_compact_game(s)


def render_game(
    start: GameState,
    moves: list[Move4D],
    *,
    format: _Format = "compact",
    force_start: bool = False,
) -> str:
    """Render a game to the chosen format (default compact).

    ``force_start`` includes the start position even when it equals
    :func:`chess4d.startpos.initial_position`; otherwise the position
    block is omitted and the parser reconstructs the default start.
    """
    _validate_format(format)
    if format == "json":
        return render_json_game(start, moves, force_start=force_start)
    return render_compact_game(start, moves, force_start=force_start)


def read_game_file(
    path: Path | str, *, format: _Format | None = None
) -> tuple[GameState, list[Move4D]]:
    """Read a game file from disk and parse it.

    The file's format defaults to whatever the extension implies
    (``.c4d`` / ``.json``); pass ``format=`` to override. UTF-8 is used
    unconditionally — chess notation is ASCII-only but the file itself
    may carry an encoding declaration that Python's ``json`` module
    handles silently.
    """
    p = Path(path)
    fmt = _resolve_format(p, format)
    text = p.read_text(encoding="utf-8")
    if fmt == "compact":
        return parse_compact_game(text)
    return parse_json_game(text)


def write_game_file(
    path: Path | str,
    start: GameState,
    moves: list[Move4D],
    *,
    format: _Format | None = None,
    force_start: bool = False,
) -> None:
    """Write a game to disk.

    ``force_start`` passes through to the underlying renderer: pass
    ``True`` to include the start position even when it equals
    :func:`chess4d.startpos.initial_position`. JSON games are written
    pretty-printed (``indent=2``) for file readability; the inline
    :func:`render_json_game` defaults to single-line.
    """
    p = Path(path)
    fmt = _resolve_format(p, format)
    if fmt == "compact":
        text = render_compact_game(start, moves, force_start=force_start)
    else:
        text = render_json_game(start, moves, force_start=force_start, indent=2)
        if not text.endswith("\n"):
            text += "\n"
    p.write_text(text, encoding="utf-8")


def read_position_file(
    path: Path | str, *, format: _Format | None = None
) -> GameState:
    """Read a standalone-position file from disk."""
    p = Path(path)
    fmt = _resolve_format(p, format)
    text = p.read_text(encoding="utf-8")
    if fmt == "compact":
        return parse_compact_position(text)
    return parse_json_position(text)


def write_position_file(
    path: Path | str,
    gs: GameState,
    *,
    format: _Format | None = None,
) -> None:
    """Write a standalone :class:`GameState` to disk as a position file."""
    p = Path(path)
    fmt = _resolve_format(p, format)
    if fmt == "compact":
        text = render_compact_position(gs)
        if not text.endswith("\n"):
            text += "\n"
    else:
        import json as _json

        from chess4d.notation.json_format import position_to_obj

        text = _json.dumps(position_to_obj(gs), indent=2) + "\n"
    p.write_text(text, encoding="utf-8")


__all__ = [
    "NotationError",
    "parse_compact_game",
    "parse_compact_move",
    "parse_compact_position",
    "parse_game",
    "parse_json_game",
    "parse_json_move",
    "parse_json_position",
    "parse_move",
    "parse_position",
    "read_game_file",
    "read_position_file",
    "render_compact_game",
    "render_compact_move",
    "render_compact_position",
    "render_game",
    "render_json_game",
    "render_json_move",
    "render_json_position",
    "render_move",
    "render_position",
    "write_game_file",
    "write_position_file",
]
