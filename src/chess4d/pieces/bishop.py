"""Bishop move generation — STUB (paper §3.7).

The bishop moves by changing exactly two coordinates by equal magnitude
(§3.7, Definition 6). Parity ``π = (x+y+z+w) mod 2`` is preserved
(§3.7, Lemma 2), which splits the bishop graph into exactly two
connected components (§3.7, Theorem 4).

Implementation lands in a later deliverable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

from chess4d.types import Color, Move4D, Square4D

if TYPE_CHECKING:
    from chess4d.board import Board4D


def bishop_moves(origin: Square4D, color: Color, board: "Board4D") -> Iterator[Move4D]:
    raise NotImplementedError("bishop_moves will be implemented in a later deliverable (paper §3.7).")
