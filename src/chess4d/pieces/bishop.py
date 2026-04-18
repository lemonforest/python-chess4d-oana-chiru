"""Bishop move generation (paper §3.7, §3.8).

A bishop displacement has exactly two nonzero components of equal
absolute value (§3.7 Definition 6). There are six coordinate planes
(§3.7 Lemma 5) — ``XY, XZ, XW, YZ, YW, ZW`` — and four sign
combinations per plane, for 24 rays per square.

Like the rook, the bishop is a slider: it walks a ray until it either
leaves the board, hits a friendly piece (stop, no capture), or hits an
enemy piece (emit a capture, then stop).

Parity behavior: every bishop move preserves ``π(x,y,z,w) = (x+y+z+w)
mod 2`` (§3.7 Lemma 2; §3.8 Prop 2(ii)), so the bishop graph splits
into exactly two connected components, one per parity class (§3.7
Theorem 4).
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator

from chess4d.geometry import BISHOP_RAYS
from chess4d.pieces._common import slide_from
from chess4d.types import Color, Move4D, Square4D

if TYPE_CHECKING:
    from chess4d.board import Board4D


def bishop_moves(origin: Square4D, color: Color, board: "Board4D") -> Iterator[Move4D]:
    """Yield pseudo-legal bishop moves from ``origin`` for the given ``color``.

    See :func:`chess4d.pieces._common.slide_from` for the shared slider
    loop. The caller is responsible for ensuring ``origin`` actually
    holds a bishop of ``color``; this function does not re-verify that.
    """
    return slide_from(BISHOP_RAYS, origin, color, board)
