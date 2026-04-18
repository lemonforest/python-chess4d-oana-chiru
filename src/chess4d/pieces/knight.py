"""Knight move generation (paper §3.8, Definitions 8 & Theorem 3).

The knight's displacement set is every permutation of ``(±2, ±1, 0, 0)``
(48 directions total). It is a **leaper**: it jumps directly to its
target, so pieces on intermediate squares never block the move. Only
the target square matters — an empty target is a move, a friendly piece
blocks (no capture), an enemy piece is captured.

Parity behavior: §3.8 Proposition 2(iii) — a knight move's coordinate-
sum delta is odd (``±2 ± 1``), so every knight move flips parity.
Interior mobility is uniformly 48 (§3.8 Theorem 3); boundary squares
are clipped by the Theorem-3 closed-form stratification.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

from chess4d.geometry import KNIGHT_NEIGHBORS
from chess4d.types import Color, Move4D, Square4D

if TYPE_CHECKING:
    from chess4d.board import Board4D


def knight_moves(origin: Square4D, color: Color, board: "Board4D") -> Iterator[Move4D]:
    """Yield pseudo-legal knight moves from ``origin`` for the given ``color``.

    Iterates :data:`KNIGHT_NEIGHBORS` directly — the slider ray-walk is
    not meaningful for a leaper, and the neighbor set already contains
    every in-bounds jump target.

    The caller is responsible for ensuring ``origin`` actually holds a
    knight of ``color``; this function does not re-verify that.
    """
    for target in KNIGHT_NEIGHBORS[origin]:
        occupant = board.occupant(target)
        if occupant is None or occupant.color != color:
            yield Move4D(from_sq=origin, to_sq=target)
