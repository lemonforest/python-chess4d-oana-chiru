"""King move generation (paper §3.9, Definition 9).

The king is a Chebyshev-1 leaper: every move is to an immediately
adjacent square (``d∞ = 1``). Standard friendly-blocks / enemy-captures
semantics apply at the target; no intermediate squares exist so the
"blocked ray" branch is moot.

Interior mobility is uniformly 80 (§3.2 Lemma 1). Castling (§3.9
Definition 10) is an X-axis move inside a single ``(z, w)``-slice whose
transit path must be safe against attackers from *any* ``(z', w')``-
slice; it requires castling-rights state and is deferred to a later
phase.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

from chess4d.geometry import KING_NEIGHBORS
from chess4d.types import Color, Move4D, Square4D

if TYPE_CHECKING:
    from chess4d.board import Board4D


def king_moves(origin: Square4D, color: Color, board: "Board4D") -> Iterator[Move4D]:
    """Yield pseudo-legal (non-castling) king moves from ``origin`` for ``color``.

    The caller is responsible for ensuring ``origin`` actually holds a
    king of ``color``; this function does not re-verify that.
    """
    for target in KING_NEIGHBORS[origin]:
        occupant = board.occupant(target)
        if occupant is None or occupant.color != color:
            yield Move4D(from_sq=origin, to_sq=target)
