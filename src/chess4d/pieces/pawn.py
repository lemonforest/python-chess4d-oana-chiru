"""Pawn move generation — STUB (paper §3.10, Definitions 11, 12, 15).

Each pawn is Y-oriented or W-oriented, fixed at initialization
(:class:`~chess4d.types.PawnAxis`). Forward and capture displacements
are parameterized by that axis so the same logic handles both
orientations. Promotion and en-passant are defined per axis; mixed
Y-vs-W en passant does not exist.

Implementation lands in a later deliverable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

from chess4d.types import Color, Move4D, Square4D

if TYPE_CHECKING:
    from chess4d.board import Board4D


def pawn_moves(origin: Square4D, color: Color, board: "Board4D") -> Iterator[Move4D]:
    raise NotImplementedError("pawn_moves will be implemented in a later deliverable (paper §3.10).")
