"""Queen move generation (paper §3.8, Definition 7).

The queen's displacement set is the union of the rook's (1-axis) and
the bishop's (2-axis). It is deliberately restricted to those two
classes; **3- or 4-axis diagonals are not queen moves** (§3.8 Def 7).
Extending the set that way would collapse rook, bishop, and queen into
a single piece class.

Blocker and capture semantics are slider-identical: a piece on a ray
stops further progress on that ray, and the queen captures an enemy on
the first blocker. Different rays are independent — a blocker on an
axis ray does not affect diagonal rays, and vice versa.

Parity behavior splits across ray types: axis (rook-type) moves flip
parity by ``d mod 2`` (§3.8 Prop 2(i)); diagonal (bishop-type) moves
preserve parity (§3.8 Prop 2(ii)).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

from chess4d.geometry import QUEEN_RAYS
from chess4d.pieces._common import slide_from
from chess4d.types import Color, Move4D, Square4D

if TYPE_CHECKING:
    from chess4d.board import Board4D


def queen_moves(origin: Square4D, color: Color, board: "Board4D") -> Iterator[Move4D]:
    """Yield pseudo-legal queen moves from ``origin`` for the given ``color``.

    See :func:`chess4d.pieces._common.slide_from` for the shared slider
    loop. The caller is responsible for ensuring ``origin`` actually
    holds a queen of ``color``; this function does not re-verify that.
    """
    return slide_from(QUEEN_RAYS, origin, color, board)
