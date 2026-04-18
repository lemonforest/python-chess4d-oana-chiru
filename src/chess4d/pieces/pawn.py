"""Pawn move generation (paper §3.10, Definitions 11-14).

Each pawn is Y-oriented or W-oriented, fixed at initialization
(:class:`~chess4d.types.PawnAxis`). Forward and capture displacements
are parameterized by that axis, so the same logic handles both
orientations; color selects the sign of the forward direction.

Emitted moves (pseudo-legal):

* One-step forward, if the target is empty (§3.10 Def 12).
* Two-step forward from the starting rank, if both the intermediate and
  target squares are empty.
* Diagonal captures in the 2D plane spanned by the x-axis and the
  pawn's forward axis, if the target holds an enemy piece (§3.10 Def
  13). Captures in XZ / YZ / ZW planes are not legal.
* Promotion: when a forward or capture move lands on the pawn's
  promotion rank, one :class:`~chess4d.types.Move4D` per promotion type
  in ``{ROOK, BISHOP, KNIGHT, QUEEN}`` is emitted (§3.10 Def 14).

En-passant (§3.10 Def 15) requires en-passant-target state and is not
implemented here.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

from chess4d.geometry import (
    PAWN_CAPTURES,
    PAWN_FORWARD_MOVES,
    PAWN_PROMOTION_RANK,
)
from chess4d.types import Color, Move4D, PawnAxis, PieceType, Square4D

if TYPE_CHECKING:
    from chess4d.board import Board4D


_PROMOTION_TYPES: tuple[PieceType, ...] = (
    PieceType.QUEEN,
    PieceType.ROOK,
    PieceType.BISHOP,
    PieceType.KNIGHT,
)


def pawn_moves(origin: Square4D, color: Color, board: "Board4D") -> Iterator[Move4D]:
    """Yield pseudo-legal (non-en-passant) pawn moves from ``origin``.

    Raises :class:`ValueError` if ``origin`` does not hold a pawn — the
    generator needs the pawn's ``pawn_axis`` and cannot infer it from
    color alone.
    """
    piece = board.occupant(origin)
    if piece is None or piece.piece_type is not PieceType.PAWN or piece.pawn_axis is None:
        raise ValueError(f"pawn_moves requires a pawn at {origin}; found {piece!r}.")
    axis: PawnAxis = piece.pawn_axis
    promotion_rank = PAWN_PROMOTION_RANK[(color, axis)]
    axis_index = int(axis)

    forward_targets = PAWN_FORWARD_MOVES[(color, axis)][origin]
    for target in forward_targets:
        if board.occupant(target) is not None:
            # Sliders-style block: once the path is obstructed, the
            # two-step (if any) beyond it is also unreachable.
            break
        yield from _emit(origin, target, axis_index, promotion_rank)

    for target in PAWN_CAPTURES[(color, axis)][origin]:
        occupant = board.occupant(target)
        if occupant is None or occupant.color == color:
            continue
        yield from _emit(origin, target, axis_index, promotion_rank)


def _emit(
    origin: Square4D, target: Square4D, axis_index: int, promotion_rank: int
) -> Iterator[Move4D]:
    if target[axis_index] == promotion_rank:
        for promo in _PROMOTION_TYPES:
            yield Move4D(from_sq=origin, to_sq=target, promotion=promo)
    else:
        yield Move4D(from_sq=origin, to_sq=target)
