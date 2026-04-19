"""Oana-Chiru starting position (paper §3.3).

The initial position places 896 pieces across 64 ``(z, w)``-slices,
partitioned into four classes:

* **Central** (``C``, 4 slices) — both colors present: 16 white + 16
  black = 32 pieces each.
* **White-only** (``W_only``, 24 slices) — only white: 16 pieces each.
* **Black-only** (``B_only``, 24 slices) — only black: 16 pieces each.
* **Empty** (``E``, 12 slices) — no pieces.

Totals: ``4·32 + 24·16 + 24·16 + 12·0 = 896``; per color ``4·16 +
24·16 = 448``; 28 kings per side.

Within a populated slice, the standard 2D layout is reproduced in the
``(x, y)`` plane: back rank ``R N B Q K B N R`` at ``y = 0`` (white) or
``y = 7`` (black), and pawns at ``y = 1`` (white) or ``y = 6`` (black).
Pawn orientation alternates with ``x`` per §3.3 / Def 11: pawns on
even ``x`` advance along the ``y`` axis (``PawnAxis.Y``); pawns on odd
``x`` advance along the ``w`` axis (``PawnAxis.W``). This alternation
is load-bearing — the Y↔W permutation is one of three generators of
the ruleset-preserving subgroup ``G_rules`` (§3.11).

Coordinate convention: the paper's §3.3 uses 1-based coordinates; the
constants below are 0-based (the package-wide convention). The two
agree up to a ``-1`` shift per axis.
"""

from __future__ import annotations

from chess4d.board import Board4D
from chess4d.state import GameState
from chess4d.types import (
    BOARD_SIZE,
    CastleSide,
    CastlingRight,
    Color,
    PawnAxis,
    Piece,
    PieceType,
    Square4D,
)


CENTRAL_SLICES: frozenset[tuple[int, int]] = frozenset(
    (z, w) for z in (3, 4) for w in (3, 4)
)
"""The 4 central ``(z, w)``-slices carrying both colors (paper §3.3).

0-based: ``{3, 4} × {3, 4}``; paper's 1-based ``{4, 5} × {4, 5}``.
"""


WHITE_ONLY_SLICES: frozenset[tuple[int, int]] = frozenset(
    [(z, w) for z in (0, 1, 2) for w in (0, 1, 2, 3)]
    + [(z, w) for z in (5, 6, 7) for w in (4, 5, 6, 7)]
)
"""The 24 ``(z, w)``-slices populated by white only (paper §3.3)."""


BLACK_ONLY_SLICES: frozenset[tuple[int, int]] = frozenset(
    [(z, w) for z in (0, 1, 2) for w in (4, 5, 6, 7)]
    + [(z, w) for z in (5, 6, 7) for w in (0, 1, 2, 3)]
)
"""The 24 ``(z, w)``-slices populated by black only (paper §3.3)."""


EMPTY_SLICES: frozenset[tuple[int, int]] = frozenset(
    (z, w) for z in (3, 4) for w in (0, 1, 2, 5, 6, 7)
)
"""The 12 empty ``(z, w)``-slices: the central ``z`` band outside the central ``w`` pair."""


_BACK_RANK: tuple[PieceType, ...] = (
    PieceType.ROOK,
    PieceType.KNIGHT,
    PieceType.BISHOP,
    PieceType.QUEEN,
    PieceType.KING,
    PieceType.BISHOP,
    PieceType.KNIGHT,
    PieceType.ROOK,
)
"""Standard 2D back-rank layout ``R N B Q K B N R`` (paper §3.3).

Applied identically in every populated slice for both colors; only the
``y`` coordinate differs (``y = 0`` for white, ``y = BOARD_SIZE - 1``
for black).
"""


def _place_color_on_slice(board: Board4D, z: int, w: int, color: Color) -> None:
    """Place one color's 16 pieces on the ``(z, w)``-slice.

    White uses ``y = 0`` (back rank) and ``y = 1`` (pawns); black uses
    ``y = BOARD_SIZE - 1`` and ``y = BOARD_SIZE - 2``. Pawn
    orientation alternates with ``x`` per §3.3 / Def 11: even ``x`` →
    :attr:`PawnAxis.Y`, odd ``x`` → :attr:`PawnAxis.W`. The eight
    ``x`` columns follow :data:`_BACK_RANK` for the back rank.
    """
    if color is Color.WHITE:
        back_y = 0
        pawn_y = 1
    else:
        back_y = BOARD_SIZE - 1
        pawn_y = BOARD_SIZE - 2
    for x, piece_type in enumerate(_BACK_RANK):
        board.place(Square4D(x, back_y, z, w), Piece(color=color, piece_type=piece_type))
    for x in range(BOARD_SIZE):
        axis = PawnAxis.Y if x % 2 == 0 else PawnAxis.W
        board.place(
            Square4D(x, pawn_y, z, w),
            Piece(color=color, piece_type=PieceType.PAWN, pawn_axis=axis),
        )


def _initial_castling_rights() -> frozenset[CastlingRight]:
    """Return the full initial castling-rights set (paper §3.9 Def 10).

    Every populated slice gets both sides of castling for its own
    color: 28 white slices × 2 sides + 28 black slices × 2 sides = 112
    rights total. Central slices contribute rights for both colors
    (they hold both kings).
    """
    rights: set[CastlingRight] = set()
    for z, w in CENTRAL_SLICES | WHITE_ONLY_SLICES:
        rights.add((Color.WHITE, z, w, CastleSide.KINGSIDE))
        rights.add((Color.WHITE, z, w, CastleSide.QUEENSIDE))
    for z, w in CENTRAL_SLICES | BLACK_ONLY_SLICES:
        rights.add((Color.BLACK, z, w, CastleSide.KINGSIDE))
        rights.add((Color.BLACK, z, w, CastleSide.QUEENSIDE))
    return frozenset(rights)


def initial_position() -> GameState:
    """Return the Oana-Chiru starting position with white to move.

    Populates the board with 896 pieces (448 per color, 28 kings per
    side) across the slice partition defined in :data:`CENTRAL_SLICES`,
    :data:`WHITE_ONLY_SLICES`, :data:`BLACK_ONLY_SLICES`, and
    :data:`EMPTY_SLICES`. Also seeds the full 112-entry castling
    rights set per :func:`_initial_castling_rights`.
    """
    board = Board4D()
    for z, w in WHITE_ONLY_SLICES:
        _place_color_on_slice(board, z, w, Color.WHITE)
    for z, w in BLACK_ONLY_SLICES:
        _place_color_on_slice(board, z, w, Color.BLACK)
    for z, w in CENTRAL_SLICES:
        _place_color_on_slice(board, z, w, Color.WHITE)
        _place_color_on_slice(board, z, w, Color.BLACK)
    return GameState(
        board=board,
        side_to_move=Color.WHITE,
        castling_rights=_initial_castling_rights(),
    )
