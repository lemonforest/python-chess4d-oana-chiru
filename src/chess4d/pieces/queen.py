"""Queen move generation — STUB (paper §3.8, Definition 7).

The queen's displacement set is the union of the rook (1-axis) and
bishop (2-axis) displacements. It is *not* extended to 3- or 4-axis
diagonals — doing so would collapse rook/bishop/queen into a single
class. See the paper §3.8 for the explicit restriction.

Implementation lands in a later deliverable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

from chess4d.types import Color, Move4D, Square4D

if TYPE_CHECKING:
    from chess4d.board import Board4D


def queen_moves(origin: Square4D, color: Color, board: "Board4D") -> Iterator[Move4D]:
    raise NotImplementedError("queen_moves will be implemented in a later deliverable (paper §3.8).")
