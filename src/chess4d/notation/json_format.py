"""Phase 7 Format B — JSON (machine-readable) notation.

The JSON format mirrors the in-memory shape of :class:`~chess4d.Move4D`
and :class:`~chess4d.GameState` directly. Where the compact format
collapses ep state into a single ``ep_target`` field and reconstructs
victim/axis by scanning the board, the JSON format keeps all three
fields (``ep_target``, ``ep_victim``, ``ep_axis``) explicit — JSON's
job is interchange with external tools, not human editing.

Move shape
----------
::

    {
      "from": [x, y, z, w],
      "to":   [x, y, z, w],
      "promotion": null | "QUEEN" | "ROOK" | "BISHOP" | "KNIGHT",
      "is_castling":   bool,
      "is_en_passant": bool
    }

``from``/``to`` are required. Boolean flags and ``promotion`` default
as shown when omitted; unknown keys raise :class:`NotationError`.

Position shape
--------------
::

    {
      "placements": [
        {"square": [x, y, z, w],
         "color":  "WHITE" | "BLACK",
         "piece_type": "PAWN" | "KNIGHT" | "BISHOP" | "ROOK" | "QUEEN" | "KING",
         "pawn_axis":  null | "Y" | "W"},
        ...
      ],
      "side_to_move":   "WHITE" | "BLACK",
      "castling_rights": [
        {"color": "WHITE" | "BLACK",
         "slice": [z, w],
         "side":  "KINGSIDE" | "QUEENSIDE"},
        ...
      ],
      "ep_target":  null | [x, y, z, w],
      "ep_victim":  null | [x, y, z, w],
      "ep_axis":    null | "Y" | "W",
      "halfmove_clock": int
    }

Placement order within the ``placements`` array is not significant
(renderer emits in canonical ``(x, y, z, w)`` order for stable output;
parser accepts any order). Ep fields are all-or-nothing: either all
three are ``null`` or all three are set.

The :class:`GameState.position_history` field is deliberately not
serialized — it is a runtime reconstruction from a move list, not part
of the position's identity. A game's history lives in the 7D game
format, replayed from ``start`` on parse.
"""

from __future__ import annotations

import json
from typing import Any, cast

from chess4d.board import Board4D
from chess4d.state import GameState
from chess4d.types import (
    BOARD_SIZE,
    CastleSide,
    CastlingRight,
    Color,
    Move4D,
    PawnAxis,
    Piece,
    PieceType,
    Square4D,
)

from chess4d.notation.errors import NotationError

# Enum name maps -------------------------------------------------------------

_COLOR_BY_NAME: dict[str, Color] = {c.name: c for c in Color}
_PIECE_TYPE_BY_NAME: dict[str, PieceType] = {p.name: p for p in PieceType}
_CASTLE_SIDE_BY_NAME: dict[str, CastleSide] = {s.name: s for s in CastleSide}
_PAWN_AXIS_BY_NAME: dict[str, PawnAxis] = {a.name: a for a in PawnAxis}

_PROMOTION_TYPES: frozenset[PieceType] = frozenset(
    {PieceType.QUEEN, PieceType.ROOK, PieceType.BISHOP, PieceType.KNIGHT}
)

_MOVE_KEYS: frozenset[str] = frozenset(
    {"from", "to", "promotion", "is_castling", "is_en_passant"}
)
_PLACEMENT_KEYS: frozenset[str] = frozenset(
    {"square", "color", "piece_type", "pawn_axis"}
)
_CASTLING_RIGHT_KEYS: frozenset[str] = frozenset({"color", "slice", "side"})
_POSITION_KEYS: frozenset[str] = frozenset(
    {
        "placements",
        "side_to_move",
        "castling_rights",
        "ep_target",
        "ep_victim",
        "ep_axis",
        "halfmove_clock",
    }
)


def _ensure_object(v: Any, where: str) -> dict[str, Any]:
    if not isinstance(v, dict):
        raise NotationError(
            f"{where} must be a JSON object, got {type(v).__name__}"
        )
    return cast(dict[str, Any], v)


def _reject_extra_keys(
    d: dict[str, Any], allowed: frozenset[str], where: str
) -> None:
    extras = set(d.keys()) - allowed
    if extras:
        raise NotationError(
            f"{where} has unexpected keys {sorted(extras)!r}; "
            f"allowed: {sorted(allowed)!r}"
        )


def _parse_int_coord_array(v: Any, where: str) -> Square4D:
    if not isinstance(v, list) or len(v) != 4:
        raise NotationError(
            f"{where} must be a 4-element array of integers, got {v!r}"
        )
    for i, x in enumerate(v):
        if isinstance(x, bool) or not isinstance(x, int):
            raise NotationError(
                f"{where}[{i}] must be an integer, got {type(x).__name__}"
            )
        if not 0 <= x < BOARD_SIZE:
            raise NotationError(
                f"{where}[{i}] = {x} out of range [0, {BOARD_SIZE})"
            )
    xs = cast(list[int], v)
    return Square4D(xs[0], xs[1], xs[2], xs[3])


def _parse_int_pair(v: Any, where: str) -> tuple[int, int]:
    if not isinstance(v, list) or len(v) != 2:
        raise NotationError(
            f"{where} must be a 2-element array of integers, got {v!r}"
        )
    for i, x in enumerate(v):
        if isinstance(x, bool) or not isinstance(x, int):
            raise NotationError(
                f"{where}[{i}] must be an integer, got {type(x).__name__}"
            )
        if not 0 <= x < BOARD_SIZE:
            raise NotationError(
                f"{where}[{i}] = {x} out of range [0, {BOARD_SIZE})"
            )
    xs = cast(list[int], v)
    return (xs[0], xs[1])


def _parse_enum(
    v: Any, table: dict[str, Any], where: str, enum_name: str
) -> Any:
    if not isinstance(v, str):
        raise NotationError(
            f"{where} must be a string, got {type(v).__name__}"
        )
    if v not in table:
        raise NotationError(
            f"{where} must be one of {sorted(table)!r} ({enum_name} name), "
            f"got {v!r}"
        )
    return table[v]


def _parse_bool(v: Any, where: str) -> bool:
    if not isinstance(v, bool):
        raise NotationError(
            f"{where} must be a boolean, got {type(v).__name__}"
        )
    return v


# Move -----------------------------------------------------------------------


def move_from_obj(obj: Any) -> Move4D:
    """Build a :class:`Move4D` from a parsed JSON object (``dict``)."""
    d = _ensure_object(obj, "move")
    _reject_extra_keys(d, _MOVE_KEYS, "move")
    if "from" not in d:
        raise NotationError("move missing required key 'from'")
    if "to" not in d:
        raise NotationError("move missing required key 'to'")
    from_sq = _parse_int_coord_array(d["from"], "move.from")
    to_sq = _parse_int_coord_array(d["to"], "move.to")
    promotion: PieceType | None = None
    if "promotion" in d and d["promotion"] is not None:
        pt = _parse_enum(
            d["promotion"], _PIECE_TYPE_BY_NAME, "move.promotion", "PieceType"
        )
        if pt not in _PROMOTION_TYPES:
            raise NotationError(
                f"move.promotion must be one of "
                f"{sorted(p.name for p in _PROMOTION_TYPES)!r}, got {pt.name!r}"
            )
        promotion = pt
    is_castling = False
    if "is_castling" in d:
        is_castling = _parse_bool(d["is_castling"], "move.is_castling")
    is_en_passant = False
    if "is_en_passant" in d:
        is_en_passant = _parse_bool(d["is_en_passant"], "move.is_en_passant")
    return Move4D(
        from_sq=from_sq,
        to_sq=to_sq,
        promotion=promotion,
        is_castling=is_castling,
        is_en_passant=is_en_passant,
    )


def move_to_obj(m: Move4D) -> dict[str, Any]:
    """Serialize :class:`Move4D` to a JSON-compatible ``dict``."""
    return {
        "from": list(m.from_sq),
        "to": list(m.to_sq),
        "promotion": m.promotion.name if m.promotion is not None else None,
        "is_castling": m.is_castling,
        "is_en_passant": m.is_en_passant,
    }


def parse_json_move(s: str) -> Move4D:
    """Parse a JSON move string into a :class:`Move4D`."""
    try:
        obj = json.loads(s)
    except json.JSONDecodeError as exc:
        raise NotationError(f"invalid JSON in move: {exc.msg}") from exc
    return move_from_obj(obj)


def render_json_move(m: Move4D) -> str:
    """Render :class:`Move4D` as a compact single-line JSON string."""
    return json.dumps(move_to_obj(m), separators=(",", ":"))


# Castling-right records -----------------------------------------------------


def _castling_right_from_obj(obj: Any, where: str) -> CastlingRight:
    d = _ensure_object(obj, where)
    _reject_extra_keys(d, _CASTLING_RIGHT_KEYS, where)
    for k in _CASTLING_RIGHT_KEYS:
        if k not in d:
            raise NotationError(f"{where} missing required key {k!r}")
    color = _parse_enum(d["color"], _COLOR_BY_NAME, f"{where}.color", "Color")
    z, w = _parse_int_pair(d["slice"], f"{where}.slice")
    side = _parse_enum(
        d["side"], _CASTLE_SIDE_BY_NAME, f"{where}.side", "CastleSide"
    )
    return (color, z, w, side)


def _castling_right_to_obj(r: CastlingRight) -> dict[str, Any]:
    color, z, w, side = r
    return {
        "color": color.name,
        "slice": [z, w],
        "side": side.name,
    }


# Placement records ----------------------------------------------------------


def _placement_from_obj(obj: Any, where: str) -> tuple[Square4D, Piece]:
    d = _ensure_object(obj, where)
    _reject_extra_keys(d, _PLACEMENT_KEYS, where)
    for k in ("square", "color", "piece_type"):
        if k not in d:
            raise NotationError(f"{where} missing required key {k!r}")
    sq = _parse_int_coord_array(d["square"], f"{where}.square")
    color = _parse_enum(d["color"], _COLOR_BY_NAME, f"{where}.color", "Color")
    piece_type = _parse_enum(
        d["piece_type"], _PIECE_TYPE_BY_NAME, f"{where}.piece_type", "PieceType"
    )
    pawn_axis: PawnAxis | None = None
    raw_axis = d.get("pawn_axis")
    if raw_axis is not None:
        pawn_axis = _parse_enum(
            raw_axis, _PAWN_AXIS_BY_NAME, f"{where}.pawn_axis", "PawnAxis"
        )
    # Piece.__post_init__ enforces the pawn/axis correlation.
    try:
        piece = Piece(color=color, piece_type=piece_type, pawn_axis=pawn_axis)
    except ValueError as exc:
        raise NotationError(f"{where}: {exc}") from exc
    return sq, piece


def _placement_to_obj(sq: Square4D, piece: Piece) -> dict[str, Any]:
    return {
        "square": list(sq),
        "color": piece.color.name,
        "piece_type": piece.piece_type.name,
        "pawn_axis": piece.pawn_axis.name if piece.pawn_axis is not None else None,
    }


# Position -------------------------------------------------------------------


def _parse_optional_coord(v: Any, where: str) -> Square4D | None:
    if v is None:
        return None
    return _parse_int_coord_array(v, where)


def position_from_obj(obj: Any) -> GameState:
    """Build a :class:`GameState` from a parsed JSON position object."""
    d = _ensure_object(obj, "position")
    _reject_extra_keys(d, _POSITION_KEYS, "position")
    for k in ("placements", "side_to_move"):
        if k not in d:
            raise NotationError(f"position missing required key {k!r}")

    placements_raw = d["placements"]
    if not isinstance(placements_raw, list):
        raise NotationError(
            f"position.placements must be an array, got "
            f"{type(placements_raw).__name__}"
        )
    board = Board4D()
    for i, entry in enumerate(placements_raw):
        sq, piece = _placement_from_obj(entry, f"position.placements[{i}]")
        board.place(sq, piece)

    side_to_move = _parse_enum(
        d["side_to_move"], _COLOR_BY_NAME, "position.side_to_move", "Color"
    )

    rights_raw = d.get("castling_rights", [])
    if not isinstance(rights_raw, list):
        raise NotationError(
            f"position.castling_rights must be an array, got "
            f"{type(rights_raw).__name__}"
        )
    rights_set: set[CastlingRight] = set()
    for i, entry in enumerate(rights_raw):
        right = _castling_right_from_obj(
            entry, f"position.castling_rights[{i}]"
        )
        if right in rights_set:
            raise NotationError(
                f"position.castling_rights[{i}] duplicates an earlier entry"
            )
        rights_set.add(right)

    ep_target = _parse_optional_coord(d.get("ep_target"), "position.ep_target")
    ep_victim = _parse_optional_coord(d.get("ep_victim"), "position.ep_victim")
    ep_axis_raw = d.get("ep_axis")
    ep_axis: PawnAxis | None = None
    if ep_axis_raw is not None:
        ep_axis = _parse_enum(
            ep_axis_raw, _PAWN_AXIS_BY_NAME, "position.ep_axis", "PawnAxis"
        )
    # All three ep fields travel together.
    ep_set = (ep_target is not None, ep_victim is not None, ep_axis is not None)
    if any(ep_set) and not all(ep_set):
        raise NotationError(
            "position ep fields must be all null or all set; got "
            f"target={ep_target!r}, victim={ep_victim!r}, axis={ep_axis!r}"
        )

    halfmove_raw = d.get("halfmove_clock", 0)
    if isinstance(halfmove_raw, bool) or not isinstance(halfmove_raw, int):
        raise NotationError(
            f"position.halfmove_clock must be an integer, got "
            f"{type(halfmove_raw).__name__}"
        )
    if halfmove_raw < 0:
        raise NotationError(
            f"position.halfmove_clock must be non-negative, got {halfmove_raw}"
        )

    return GameState(
        board=board,
        side_to_move=side_to_move,
        castling_rights=frozenset(rights_set),
        ep_target=ep_target,
        ep_victim=ep_victim,
        ep_axis=ep_axis,
        halfmove_clock=halfmove_raw,
    )


def position_to_obj(gs: GameState) -> dict[str, Any]:
    """Serialize a :class:`GameState` to a JSON-compatible ``dict``."""
    sorted_squares = sorted(gs.board._squares.keys())
    placements = [
        _placement_to_obj(sq, gs.board._squares[sq]) for sq in sorted_squares
    ]
    ordered_rights = sorted(
        gs.castling_rights,
        key=lambda r: (int(r[0]), r[1], r[2], int(r[3])),
    )
    rights = [_castling_right_to_obj(r) for r in ordered_rights]
    return {
        "placements": placements,
        "side_to_move": gs.side_to_move.name,
        "castling_rights": rights,
        "ep_target": list(gs.ep_target) if gs.ep_target is not None else None,
        "ep_victim": list(gs.ep_victim) if gs.ep_victim is not None else None,
        "ep_axis": gs.ep_axis.name if gs.ep_axis is not None else None,
        "halfmove_clock": gs.halfmove_clock,
    }


def parse_json_position(s: str) -> GameState:
    """Parse a JSON position string into a :class:`GameState`."""
    try:
        obj = json.loads(s)
    except json.JSONDecodeError as exc:
        raise NotationError(f"invalid JSON in position: {exc.msg}") from exc
    return position_from_obj(obj)


def render_json_position(gs: GameState) -> str:
    """Render a :class:`GameState` as a compact single-line JSON string."""
    return json.dumps(position_to_obj(gs), separators=(",", ":"))


# Game -----------------------------------------------------------------------

_GAME_KEYS: frozenset[str] = frozenset({"start", "moves"})


def game_from_obj(obj: Any) -> tuple[GameState, list[Move4D]]:
    """Build ``(start_state, move_list)`` from a parsed JSON game object.

    ``start`` may be ``null`` (game starts from
    :func:`chess4d.startpos.initial_position`) or a nested position
    object. ``moves`` is an array of move objects. Moves are returned
    unreplayed.
    """
    from chess4d.startpos import initial_position

    d = _ensure_object(obj, "game")
    _reject_extra_keys(d, _GAME_KEYS, "game")
    if "moves" not in d:
        raise NotationError("game missing required key 'moves'")

    start_raw = d.get("start")
    if start_raw is None:
        start = initial_position()
    else:
        start = position_from_obj(start_raw)

    moves_raw = d["moves"]
    if not isinstance(moves_raw, list):
        raise NotationError(
            f"game.moves must be an array, got {type(moves_raw).__name__}"
        )
    moves: list[Move4D] = []
    for i, entry in enumerate(moves_raw):
        try:
            moves.append(move_from_obj(entry))
        except NotationError as exc:
            raise NotationError(f"game.moves[{i}]: {exc}") from exc
    return start, moves


def game_to_obj(
    start: GameState,
    moves: list[Move4D],
    *,
    force_start: bool = False,
) -> dict[str, Any]:
    """Serialize a game to a JSON-compatible ``dict``.

    If ``start`` is equivalent to :func:`chess4d.startpos.initial_position`
    and ``force_start`` is ``False``, ``start`` is emitted as ``null``
    (the parser defaults to ``initial_position()`` on ``null``).
    Otherwise the full position object is emitted.
    """
    from chess4d.notation.compact import _game_starts_from_initial

    if force_start or not _game_starts_from_initial(start):
        start_obj: dict[str, Any] | None = position_to_obj(start)
    else:
        start_obj = None
    return {
        "start": start_obj,
        "moves": [move_to_obj(m) for m in moves],
    }


def parse_json_game(s: str) -> tuple[GameState, list[Move4D]]:
    """Parse a JSON game string into ``(start_state, move_list)``."""
    try:
        obj = json.loads(s)
    except json.JSONDecodeError as exc:
        raise NotationError(f"invalid JSON in game: {exc.msg}") from exc
    return game_from_obj(obj)


def render_json_game(
    start: GameState,
    moves: list[Move4D],
    *,
    force_start: bool = False,
    indent: int | None = None,
) -> str:
    """Render a game as a JSON string.

    ``indent`` mirrors :func:`json.dumps` — pass an integer to
    pretty-print, or leave as ``None`` for a single-line compact form.
    Game files on disk typically use ``indent=2``; in-memory interchange
    uses the compact default.
    """
    obj = game_to_obj(start, moves, force_start=force_start)
    if indent is None:
        return json.dumps(obj, separators=(",", ":"))
    return json.dumps(obj, indent=indent)
