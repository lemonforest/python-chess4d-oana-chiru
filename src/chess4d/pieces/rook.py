"""Rook move generation (paper §3.5).

The rook's displacement set is ``{±e_x, ±e_y, ±e_z, ±e_w}``. From any
square, it slides along one of these eight directions until it either:

* leaves the board, or
* encounters a square occupied by a friendly piece (stop, no capture), or
* encounters a square occupied by an opposing piece (emit a capture move,
  then stop).

Empty-board mobility is uniformly 28 (§3.5, Corollary 1). The rook graph
is the Hamming graph ``H(4, 8)`` (§3.5, Theorem 2).

Parity behavior: a rook move of length ``d`` along a single axis flips
parity by ``d mod 2`` (§3.8, Proposition 2(i)).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

from chess4d.geometry import ROOK_RAYS
from chess4d.pieces._common import slide_from
from chess4d.types import Color, Move4D, Square4D

if TYPE_CHECKING:
    from chess4d.board import Board4D


def rook_moves(origin: Square4D, color: Color, board: "Board4D") -> Iterator[Move4D]:
    """Yield pseudo-legal rook moves from ``origin`` for the given ``color``.

    See :func:`chess4d.pieces._common.slide_from` for the shared slider
    loop. The caller is responsible for ensuring ``origin`` actually
    holds a rook of ``color``; this function does not re-verify that.
    """
    return slide_from(ROOK_RAYS, origin, color, board)
