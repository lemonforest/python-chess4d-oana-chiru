"""Knight move generation — STUB (paper §3.8, Definition 8).

The knight's displacement set is the permutations of ``(±2, ±1, 0, 0)``;
maximum mobility is 48 (§3.8). Knight moves always flip parity
(Proposition 2(iii)).

Implementation lands in a later deliverable.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

from chess4d.types import Color, Move4D, Square4D

if TYPE_CHECKING:
    from chess4d.board import Board4D


def knight_moves(origin: Square4D, color: Color, board: "Board4D") -> Iterator[Move4D]:
    raise NotImplementedError("knight_moves will be implemented in a later deliverable (paper §3.8).")
