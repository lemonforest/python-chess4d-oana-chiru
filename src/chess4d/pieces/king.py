"""King move generation — STUB (paper §3.9, Definition 9).

The king moves to any Chebyshev-adjacent square (``d∞ = 1``); maximum
mobility is 80 on an interior square (§3.2, Lemma 1 and §3.9).
Castling (§3.9, Definition 10) is an X-axis move within a single
``(z, w)``-slice, and the king's transit path must be safe against
attackers from *any* ``(z', w')``-slice.

Implementation lands in a later deliverable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

from chess4d.types import Color, Move4D, Square4D

if TYPE_CHECKING:
    from chess4d.board import Board4D


def king_moves(origin: Square4D, color: Color, board: "Board4D") -> Iterator[Move4D]:
    raise NotImplementedError("king_moves will be implemented in a later deliverable (paper §3.9).")
