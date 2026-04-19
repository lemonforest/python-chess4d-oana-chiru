"""Phase 7 Format A — compact (human-readable) notation.

Coordinate encoding
-------------------
A square is four characters in ``(x, y, z, w)`` order:

* x-axis: lowercase letter ``a``–``h`` (``a`` ↔ 0, ``h`` ↔ 7)
* y-axis: digit ``1``–``8`` (``1`` ↔ 0, ``8`` ↔ 7)
* z-axis: lowercase letter ``a``–``h``
* w-axis: digit ``1``–``8``

The letter/digit/letter/digit pattern is strictly positional: ``a1c4``
is unambiguously ``Square4D(x=0, y=0, z=2, w=3)``. Because coordinate
letters are drawn from ``a``–``h`` only, the letter ``x`` never appears
inside a coordinate — so ``x`` is a safe capture marker between two
coordinates and can never be confused for part of either.

Move grammar
------------
::

    <move>       ::= <ordinary> | <capture> | <castling> | <ep>
    <ordinary>   ::= <from>-<to>[=<promo>]
    <capture>    ::= <from>x<to>[=<promo>]
    <castling>   ::= ("O-O" | "O-O-O" | "o-o" | "o-o-o") "@" <slice>
    <ep>         ::= <from>x<to>"ep"
    <from>, <to> ::= 4-character coordinate
    <slice>      ::= 2-character (z, w) coordinate
    <promo>      ::= "Q" | "R" | "B" | "N"

The capture marker (``x``) is informational only — the parser accepts
either ``-`` or ``x`` between the two coordinates and records nothing
about capture status on the returned :class:`~chess4d.Move4D`. The
renderer emits ``x`` when the caller flags the move as a capture.

Castling encodes its color by case: uppercase ``O`` for white,
lowercase ``o`` for black. This matches the uppercase/lowercase piece
convention used by the position format (7B) and keeps
:func:`parse_compact_move` self-contained — no side-to-move context
needs to be threaded through to resolve castling moves.

Promotion characters are case-sensitive: ``Q``/``R``/``B``/``N`` only.
Lowercase promotion letters are rejected.

Position grammar
----------------
A position file begins with a single header line and is followed by
zero or more slice lines (one per non-empty ``(z, w)``-slice)::

    <header>      ::= <side> " " <castling> " " <ep> " " <halfmove>
    <slice-line>  ::= <slice-key> ": " <rank0> "/" <rank1> "/" ... "/" <rank7>
    <slice-key>   ::= 2-character (z, w) coordinate
    <rank>        ::= 8 characters (x = 0..7) from the piece-char set
    <side>        ::= "w" | "b"   (case-insensitive on parse)
    <castling>    ::= "-" | <right> ("," <right>)*
    <right>       ::= <color_ch> <slice-key> <side_ch>
    <color_ch>    ::= "W" | "B"
    <side_ch>     ::= "K" | "Q"
    <ep>          ::= "-" | 4-character coordinate
    <halfmove>    ::= decimal integer (unsigned)

Rank order within a slice is ascending ``y`` — ``rank0`` is the white
back rank (``y = 0``), ``rank7`` is the black back rank (``y = 7``).
Omitted slices are empty by definition; a slice with at least one
piece must be listed in full. The renderer emits slices in
``(z, w)``-major order and never emits empty slices; the parser
accepts slices in any order and accepts an explicit ``<slice-key>:
empty`` line as a synonym for omission.

Piece characters
~~~~~~~~~~~~~~~~

============  ==================================
``.``         empty square
``R/N/B/Q/K`` white rook / knight / bishop / queen / king
``r/n/b/q/k`` black (same)
``Y``         white Y-oriented pawn
``W``         white W-oriented pawn
``y``         black Y-oriented pawn
``w``         black W-oriented pawn
============  ==================================

All pawns must specify their axis via ``Y``/``W``/``y``/``w``; a plain
``P``/``p`` is not accepted. Promoted pieces drop their pawn marker and
use the new piece's letter.
"""

from __future__ import annotations

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


_LETTER_MIN = "a"
_LETTER_MAX = "h"
_DIGIT_MIN = "1"
_DIGIT_MAX = "8"

_PROMOTION_BY_CHAR: dict[str, PieceType] = {
    "Q": PieceType.QUEEN,
    "R": PieceType.ROOK,
    "B": PieceType.BISHOP,
    "N": PieceType.KNIGHT,
}

_CHAR_BY_PROMOTION: dict[PieceType, str] = {v: k for k, v in _PROMOTION_BY_CHAR.items()}


def _parse_letter(ch: str, field: str) -> int:
    """Parse a single ``a``-``h`` character to its 0-based coordinate."""
    if len(ch) != 1 or not (_LETTER_MIN <= ch <= _LETTER_MAX):
        raise NotationError(
            f"expected letter a-h for {field}, got {ch!r}"
        )
    return ord(ch) - ord(_LETTER_MIN)


def _parse_digit(ch: str, field: str) -> int:
    """Parse a single ``1``-``8`` character to its 0-based coordinate."""
    if len(ch) != 1 or not (_DIGIT_MIN <= ch <= _DIGIT_MAX):
        raise NotationError(
            f"expected digit 1-8 for {field}, got {ch!r}"
        )
    return int(ch) - 1


def _parse_coord(s: str, field: str) -> Square4D:
    """Parse a 4-character coordinate into a :class:`~chess4d.Square4D`."""
    if len(s) != 4:
        raise NotationError(
            f"{field} coordinate must be exactly 4 characters, got {s!r}"
        )
    return Square4D(
        _parse_letter(s[0], f"{field}.x"),
        _parse_digit(s[1], f"{field}.y"),
        _parse_letter(s[2], f"{field}.z"),
        _parse_digit(s[3], f"{field}.w"),
    )


def _render_letter(v: int) -> str:
    return chr(ord(_LETTER_MIN) + v)


def _render_digit(v: int) -> str:
    return str(v + 1)


def _render_coord(sq: Square4D) -> str:
    """Render a :class:`~chess4d.Square4D` as a 4-character coordinate."""
    return (
        _render_letter(sq.x)
        + _render_digit(sq.y)
        + _render_letter(sq.z)
        + _render_digit(sq.w)
    )


def _parse_slice(s: str) -> tuple[int, int]:
    """Parse a 2-character ``(z, w)`` coordinate."""
    if len(s) != 2:
        raise NotationError(
            f"slice must be exactly 2 characters, got {s!r}"
        )
    return _parse_letter(s[0], "slice.z"), _parse_digit(s[1], "slice.w")


def _render_slice(z: int, w: int) -> str:
    return _render_letter(z) + _render_digit(w)


def _parse_castle(s: str) -> Move4D:
    """Parse a castling move (e.g. ``O-O@c4``, ``o-o-o@d4``)."""
    at = s.find("@")
    if at < 0:
        raise NotationError(
            f"castling move missing '@<slice>' suffix: {s!r}"
        )
    castle_part = s[:at]
    slice_part = s[at + 1:]
    if castle_part == "O-O":
        color, side = Color.WHITE, CastleSide.KINGSIDE
    elif castle_part == "O-O-O":
        color, side = Color.WHITE, CastleSide.QUEENSIDE
    elif castle_part == "o-o":
        color, side = Color.BLACK, CastleSide.KINGSIDE
    elif castle_part == "o-o-o":
        color, side = Color.BLACK, CastleSide.QUEENSIDE
    else:
        raise NotationError(
            f"invalid castling token {castle_part!r}: "
            "expected 'O-O', 'O-O-O', 'o-o', or 'o-o-o'"
        )
    z, w = _parse_slice(slice_part)
    back_y = 0 if color is Color.WHITE else BOARD_SIZE - 1
    to_x = 6 if side is CastleSide.KINGSIDE else 2
    return Move4D(
        from_sq=Square4D(4, back_y, z, w),
        to_sq=Square4D(to_x, back_y, z, w),
        is_castling=True,
    )


def _render_castle(m: Move4D) -> str:
    """Render a castling :class:`~chess4d.Move4D` as compact notation."""
    if m.from_sq.x != 4 or m.to_sq.x not in (2, 6):
        raise ValueError(
            f"cannot render castling move with x={m.from_sq.x}->{m.to_sq.x}; "
            "expected from.x=4 and to.x in (2, 6)"
        )
    if m.from_sq.y not in (0, BOARD_SIZE - 1):
        raise ValueError(
            f"cannot render castling move with from.y={m.from_sq.y}; "
            f"expected 0 (white) or {BOARD_SIZE - 1} (black)"
        )
    if (m.from_sq.y, m.from_sq.z, m.from_sq.w) != (m.to_sq.y, m.to_sq.z, m.to_sq.w):
        raise ValueError(
            "cannot render castling move that leaves its (y, z, w) slice"
        )
    is_white = m.from_sq.y == 0
    kingside = m.to_sq.x == 6
    o = "O" if is_white else "o"
    base = f"{o}-{o}" if kingside else f"{o}-{o}-{o}"
    return f"{base}@{_render_slice(m.from_sq.z, m.from_sq.w)}"


def parse_compact_move(s: str) -> Move4D:
    """Parse a compact-notation move string into a :class:`~chess4d.Move4D`.

    Accepts any of the four grammar branches (ordinary, capture,
    castling, en passant). Raises :class:`NotationError` for any
    syntactic problem; the error message names the failing field.

    This function performs *syntactic* validation only. It does not
    check that the resulting move is legal in any particular position,
    nor that (for instance) a promotion target is on the terminal rank.
    Semantic validation belongs to :meth:`chess4d.GameState.push`.
    """
    if not s:
        raise NotationError("empty move string")
    if s[0] in ("O", "o"):
        return _parse_castle(s)
    if len(s) < 9:
        raise NotationError(
            f"move too short: {s!r} (need at least 9 characters for "
            "'<from><sep><to>')"
        )
    from_sq = _parse_coord(s[0:4], "from")
    sep = s[4]
    if sep not in ("-", "x"):
        raise NotationError(
            f"expected '-' or 'x' separator at position 4, got {sep!r} in {s!r}"
        )
    to_sq = _parse_coord(s[5:9], "to")
    tail = s[9:]
    promotion: PieceType | None = None
    is_en_passant = False
    if tail == "":
        pass
    elif tail == "ep":
        if sep != "x":
            raise NotationError(
                f"en-passant suffix 'ep' requires 'x' capture marker, "
                f"found '-' in {s!r}"
            )
        is_en_passant = True
    elif tail.startswith("=") and len(tail) == 2:
        promo_char = tail[1]
        if promo_char not in _PROMOTION_BY_CHAR:
            raise NotationError(
                f"expected promotion piece Q/R/B/N, got {promo_char!r} in {s!r}"
            )
        promotion = _PROMOTION_BY_CHAR[promo_char]
    else:
        raise NotationError(
            f"unexpected trailing characters {tail!r} after move body in {s!r}"
        )
    return Move4D(
        from_sq=from_sq,
        to_sq=to_sq,
        promotion=promotion,
        is_en_passant=is_en_passant,
    )


def render_compact_move(m: Move4D, *, is_capture: bool = False) -> str:
    """Render a :class:`~chess4d.Move4D` as a compact-notation string.

    The ``is_capture`` flag selects the ``x`` separator for ordinary
    capturing moves; en-passant captures always render with ``x``
    regardless of the flag. For castling moves the flag is ignored.
    The flag is the caller's responsibility: a move's :class:`Move4D`
    does not carry the captured piece's identity, so the caller must
    track capture status externally (typically by looking at the
    destination square on the pre-move board).
    """
    if m.is_castling:
        return _render_castle(m)
    sep = "x" if (is_capture or m.is_en_passant) else "-"
    core = f"{_render_coord(m.from_sq)}{sep}{_render_coord(m.to_sq)}"
    if m.is_en_passant:
        return core + "ep"
    if m.promotion is not None:
        return core + "=" + _CHAR_BY_PROMOTION[m.promotion]
    return core


# Position notation ----------------------------------------------------------

_PIECE_BY_CHAR: dict[str, Piece] = {
    "R": Piece(Color.WHITE, PieceType.ROOK),
    "N": Piece(Color.WHITE, PieceType.KNIGHT),
    "B": Piece(Color.WHITE, PieceType.BISHOP),
    "Q": Piece(Color.WHITE, PieceType.QUEEN),
    "K": Piece(Color.WHITE, PieceType.KING),
    "Y": Piece(Color.WHITE, PieceType.PAWN, PawnAxis.Y),
    "W": Piece(Color.WHITE, PieceType.PAWN, PawnAxis.W),
    "r": Piece(Color.BLACK, PieceType.ROOK),
    "n": Piece(Color.BLACK, PieceType.KNIGHT),
    "b": Piece(Color.BLACK, PieceType.BISHOP),
    "q": Piece(Color.BLACK, PieceType.QUEEN),
    "k": Piece(Color.BLACK, PieceType.KING),
    "y": Piece(Color.BLACK, PieceType.PAWN, PawnAxis.Y),
    "w": Piece(Color.BLACK, PieceType.PAWN, PawnAxis.W),
}

_CHAR_BY_PIECE: dict[Piece, str] = {v: k for k, v in _PIECE_BY_CHAR.items()}

_EMPTY_CHAR = "."


def _parse_piece_char(ch: str, where: str) -> Piece | None:
    """Return the :class:`Piece` for a rank character, or ``None`` for empty."""
    if ch == _EMPTY_CHAR:
        return None
    piece = _PIECE_BY_CHAR.get(ch)
    if piece is None:
        raise NotationError(
            f"unknown piece character {ch!r} at {where} "
            f"(expected one of '{_EMPTY_CHAR}' or R/N/B/Q/K/Y/W/r/n/b/q/k/y/w)"
        )
    return piece


def _render_piece(piece: Piece | None) -> str:
    if piece is None:
        return _EMPTY_CHAR
    return _CHAR_BY_PIECE[piece]


def _parse_castling_rights(s: str) -> frozenset[CastlingRight]:
    """Parse the header ``<castling>`` token into a castling-rights set."""
    if s == "-":
        return frozenset()
    rights: set[CastlingRight] = set()
    for token in s.split(","):
        if len(token) != 4:
            raise NotationError(
                f"castling-right token must be 4 characters (color+slice+side), "
                f"got {token!r}"
            )
        color_ch = token[0]
        if color_ch == "W":
            color = Color.WHITE
        elif color_ch == "B":
            color = Color.BLACK
        else:
            raise NotationError(
                f"castling-right color must be 'W' or 'B', got {color_ch!r} "
                f"in {token!r}"
            )
        z, w = _parse_slice(token[1:3])
        side_ch = token[3]
        if side_ch == "K":
            side = CastleSide.KINGSIDE
        elif side_ch == "Q":
            side = CastleSide.QUEENSIDE
        else:
            raise NotationError(
                f"castling-right side must be 'K' or 'Q', got {side_ch!r} "
                f"in {token!r}"
            )
        right: CastlingRight = (color, z, w, side)
        if right in rights:
            raise NotationError(
                f"duplicate castling right {token!r} in rights string"
            )
        rights.add(right)
    return frozenset(rights)


def _render_castling_rights(rights: frozenset[CastlingRight]) -> str:
    """Render the castling-rights set in canonical ``(color, z, w, side)`` order."""
    if not rights:
        return "-"
    ordered = sorted(rights, key=lambda r: (int(r[0]), r[1], r[2], int(r[3])))
    parts: list[str] = []
    for color, z, w, side in ordered:
        color_ch = "W" if color is Color.WHITE else "B"
        side_ch = "K" if side is CastleSide.KINGSIDE else "Q"
        parts.append(f"{color_ch}{_render_slice(z, w)}{side_ch}")
    return ",".join(parts)


def _parse_rank_line(s: str, z: int, w: int, y: int) -> list[tuple[Square4D, Piece]]:
    """Parse an 8-character rank line into ``(square, piece)`` placements."""
    if len(s) != BOARD_SIZE:
        raise NotationError(
            f"rank line for slice ({z}, {w}) y={y} must be {BOARD_SIZE} characters, "
            f"got {len(s)} in {s!r}"
        )
    out: list[tuple[Square4D, Piece]] = []
    for x, ch in enumerate(s):
        piece = _parse_piece_char(ch, f"slice ({z}, {w}) y={y} x={x}")
        if piece is not None:
            out.append((Square4D(x, y, z, w), piece))
    return out


def _render_rank_line(board: Board4D, z: int, w: int, y: int) -> str:
    chars: list[str] = []
    for x in range(BOARD_SIZE):
        chars.append(_render_piece(board.occupant(Square4D(x, y, z, w))))
    return "".join(chars)


def _slice_is_empty(board: Board4D, z: int, w: int) -> bool:
    for y in range(BOARD_SIZE):
        for x in range(BOARD_SIZE):
            if board.occupant(Square4D(x, y, z, w)) is not None:
                return False
    return True


def _reconstruct_ep(
    board: Board4D, ep_target: Square4D, side_to_move: Color
) -> tuple[Square4D, PawnAxis]:
    """Derive ``(ep_victim, ep_axis)`` from an ep-target coordinate.

    The victim of an en-passant capture is the pawn whose 2-step
    created the target — it sits one square past ``ep_target`` along
    its own ``pawn_axis``, on the side-to-move's enemy. There is at
    most one such pawn for a well-formed position (produced by a
    single 2-step move from the previous ply); the parser raises
    :class:`NotationError` otherwise.
    """
    enemy = Color(1 - side_to_move)
    candidates: list[tuple[Square4D, PawnAxis]] = []
    for axis in (PawnAxis.Y, PawnAxis.W):
        axis_idx = int(axis)
        for step in (-1, 1):
            coords = list(ep_target)
            coords[axis_idx] += step
            victim_sq = Square4D(coords[0], coords[1], coords[2], coords[3])
            if not victim_sq.in_bounds():
                continue
            piece = board.occupant(victim_sq)
            if piece is None or piece.piece_type is not PieceType.PAWN:
                continue
            if piece.color is not enemy:
                continue
            if piece.pawn_axis is not axis:
                continue
            candidates.append((victim_sq, axis))
    if not candidates:
        raise NotationError(
            f"ep_target {_render_coord(ep_target)} has no adjacent enemy pawn "
            "whose axis could have produced it"
        )
    if len(candidates) > 1:
        raise NotationError(
            f"ep_target {_render_coord(ep_target)} is ambiguous: "
            f"{len(candidates)} candidate victims exist"
        )
    return candidates[0]


def _parse_header(
    line: str,
) -> tuple[Color, frozenset[CastlingRight], Square4D | None, int]:
    """Parse the header line into ``(side, rights, ep_target, halfmove)``."""
    parts = line.split()
    if len(parts) != 4:
        raise NotationError(
            f"header must have 4 space-separated fields "
            f"(side, castling, ep, halfmove), got {len(parts)} in {line!r}"
        )
    side_tok, castle_tok, ep_tok, half_tok = parts
    side_lower = side_tok.lower()
    if side_lower == "w":
        side = Color.WHITE
    elif side_lower == "b":
        side = Color.BLACK
    else:
        raise NotationError(
            f"side-to-move must be 'w' or 'b', got {side_tok!r}"
        )
    rights = _parse_castling_rights(castle_tok)
    ep_target: Square4D | None
    if ep_tok == "-":
        ep_target = None
    else:
        ep_target = _parse_coord(ep_tok, "ep")
    try:
        halfmove = int(half_tok)
    except ValueError as exc:
        raise NotationError(
            f"halfmove clock must be a decimal integer, got {half_tok!r}"
        ) from exc
    if halfmove < 0:
        raise NotationError(
            f"halfmove clock must be non-negative, got {halfmove}"
        )
    return side, rights, ep_target, halfmove


def _render_header(gs: GameState) -> str:
    side_ch = "w" if gs.side_to_move is Color.WHITE else "b"
    castle = _render_castling_rights(gs.castling_rights)
    ep = _render_coord(gs.ep_target) if gs.ep_target is not None else "-"
    return f"{side_ch} {castle} {ep} {gs.halfmove_clock}"


def parse_compact_position(s: str) -> GameState:
    """Parse a compact-notation position into a :class:`~chess4d.GameState`.

    The input may contain blank lines between the header and any slice
    line, and trailing whitespace on any line is ignored. An explicit
    ``<slice-key>: empty`` marker is accepted as a synonym for "slice
    omitted" — both produce the same empty ``(z, w)`` slab.

    Ep-state reconstruction: the header carries only ``ep_target``; the
    parser derives ``ep_victim`` and ``ep_axis`` from the board (see
    :func:`_reconstruct_ep`). If the ep target is present but no enemy
    pawn is adjacent along a single axis, the parse fails.
    """
    lines = [ln.rstrip() for ln in s.splitlines()]
    lines = [ln for ln in lines if ln.strip() != ""]
    if not lines:
        raise NotationError("position is empty (no header line)")
    side, rights, ep_target, halfmove = _parse_header(lines[0])
    board = Board4D()
    seen_slices: set[tuple[int, int]] = set()
    for raw in lines[1:]:
        key_sep = raw.find(":")
        if key_sep < 0:
            raise NotationError(
                f"slice line missing ':' separator: {raw!r}"
            )
        slice_key = raw[:key_sep].strip()
        body = raw[key_sep + 1:].strip()
        if len(slice_key) != 2:
            raise NotationError(
                f"slice key must be 2 characters, got {slice_key!r} in {raw!r}"
            )
        z, w = _parse_slice(slice_key)
        if (z, w) in seen_slices:
            raise NotationError(
                f"slice ({z}, {w}) listed more than once"
            )
        seen_slices.add((z, w))
        if body == "empty":
            continue
        rank_lines = body.split("/")
        if len(rank_lines) != BOARD_SIZE:
            raise NotationError(
                f"slice ({z}, {w}) must have {BOARD_SIZE} ranks separated by '/', "
                f"got {len(rank_lines)} in {body!r}"
            )
        for y, rank in enumerate(rank_lines):
            for sq, piece in _parse_rank_line(rank, z, w, y):
                board.place(sq, piece)
    ep_victim: Square4D | None = None
    ep_axis: PawnAxis | None = None
    if ep_target is not None:
        ep_victim, ep_axis = _reconstruct_ep(board, ep_target, side)
    return GameState(
        board=board,
        side_to_move=side,
        castling_rights=rights,
        ep_target=ep_target,
        ep_victim=ep_victim,
        ep_axis=ep_axis,
        halfmove_clock=halfmove,
    )


def render_compact_position(gs: GameState) -> str:
    """Render a :class:`~chess4d.GameState` as compact-notation text.

    The output is the header line followed by one line per non-empty
    ``(z, w)``-slice, in ``(z, w)``-major order. Slices that contain no
    pieces are omitted — the parser treats omission as empty, and for
    a fully-empty board the rendered output is just the header line.
    """
    board = gs.board
    out: list[str] = [_render_header(gs)]
    for z in range(BOARD_SIZE):
        for w in range(BOARD_SIZE):
            if _slice_is_empty(board, z, w):
                continue
            ranks = [_render_rank_line(board, z, w, y) for y in range(BOARD_SIZE)]
            out.append(f"{_render_slice(z, w)}: {'/'.join(ranks)}")
    return "\n".join(out)


# Game notation --------------------------------------------------------------


def _strip_comments_and_blanks(s: str) -> list[str]:
    """Return non-blank, non-comment lines ``rstrip``'d of trailing space.

    Lines whose first non-whitespace character is ``#`` are treated as
    comments; blank lines (whitespace-only) are skipped. Any other
    leading whitespace is preserved so that callers can still see the
    shape of the line for downstream parsing.
    """
    out: list[str] = []
    for raw in s.splitlines():
        trimmed = raw.rstrip()
        if trimmed.strip() == "":
            continue
        if trimmed.lstrip().startswith("#"):
            continue
        out.append(trimmed)
    return out


def _line_is_position_header(line: str) -> bool:
    """True iff ``line`` looks like a compact-position header line.

    A compact-position header has exactly four space-separated tokens
    and its side-to-move token is a single ``w``/``b`` (case-insensitive).
    Compact moves never have whitespace inside a token, so this test
    cleanly distinguishes the two without trying a parse.
    """
    parts = line.strip().split()
    if len(parts) != 4:
        return False
    return parts[0] in ("w", "b", "W", "B")


def _line_is_slice_body(line: str) -> bool:
    """True iff ``line`` looks like a compact-position slice-body line.

    Slice lines are ``<z><w>: <rank>/.../<rank>`` or the shorthand
    ``<z><w>: empty`` — a 2-char key (letter + digit) followed by
    ``:``. Compact moves never contain ``:``.
    """
    if ":" not in line:
        return False
    key = line.split(":", 1)[0].strip()
    if len(key) != 2:
        return False
    return ("a" <= key[0] <= "h") and ("1" <= key[1] <= "8")


def parse_compact_game(s: str) -> tuple[GameState, list[Move4D]]:
    """Parse a compact-game string into ``(start_state, move_list)``.

    A compact game is:

    * Zero or more ``#``-prefixed comment lines (ignored) and blank
      lines (ignored), interleaved anywhere.
    * An optional start-position block — the header line plus any
      consecutive slice-body lines. If the first non-comment line is
      not a position header, the start defaults to
      :func:`chess4d.startpos.initial_position`.
    * Zero or more move lines, one compact move per line.

    Moves are returned unreplayed: the caller is responsible for
    advancing the returned ``start_state`` through the move list if a
    post-game state is needed. Per-move parse errors are wrapped with
    the move's 1-based index for diagnostics.
    """
    from chess4d.startpos import initial_position

    meaningful = _strip_comments_and_blanks(s)
    if not meaningful:
        return initial_position(), []

    if _line_is_position_header(meaningful[0]):
        pos_lines = [meaningful[0]]
        i = 1
        while i < len(meaningful) and _line_is_slice_body(meaningful[i]):
            pos_lines.append(meaningful[i])
            i += 1
        start = parse_compact_position("\n".join(pos_lines))
        move_lines = meaningful[i:]
    else:
        start = initial_position()
        move_lines = meaningful

    moves: list[Move4D] = []
    for idx, line in enumerate(move_lines, start=1):
        try:
            moves.append(parse_compact_move(line.strip()))
        except NotationError as exc:
            raise NotationError(
                f"move #{idx} ({line.strip()!r}): {exc}"
            ) from exc
    return start, moves


def render_compact_game(
    start: GameState,
    moves: list[Move4D],
    *,
    force_start: bool = False,
) -> str:
    """Render a ``(start, moves)`` game to a compact-game string.

    If ``start`` is equivalent to :func:`chess4d.startpos.initial_position`
    the position block is omitted — the parser defaults to
    ``initial_position()`` when no header is present. Pass
    ``force_start=True`` to always emit the position block (useful for
    explicit round-trip tests).

    The move separator (``-`` vs ``x``) is chosen by replaying ``moves``
    onto a deep copy of ``start`` to determine whether each destination
    was occupied pre-move. Replay uses the full legality pipeline; an
    illegal move in the list will surface as
    :class:`~chess4d.errors.IllegalMoveError`.
    """
    from copy import deepcopy

    lines: list[str] = []
    include_start = force_start or not _game_starts_from_initial(start)
    if include_start:
        lines.append(render_compact_position(start))

    replay = deepcopy(start)
    for m in moves:
        is_capture = replay.board.occupant(m.to_sq) is not None
        lines.append(render_compact_move(m, is_capture=is_capture))
        replay.push(m)
    return "\n".join(lines) + ("\n" if lines else "")


def _game_starts_from_initial(gs: GameState) -> bool:
    """True iff ``gs`` is a freshly-built initial position."""
    from chess4d.startpos import initial_position

    ref = initial_position()
    return (
        gs.board == ref.board
        and gs.side_to_move is ref.side_to_move
        and gs.castling_rights == ref.castling_rights
        and gs.ep_target == ref.ep_target
        and gs.ep_victim == ref.ep_victim
        and gs.ep_axis is ref.ep_axis
        and gs.halfmove_clock == ref.halfmove_clock
    )
