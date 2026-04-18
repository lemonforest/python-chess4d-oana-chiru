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
from chess4d.types import Color, Move4D, Square4D

if TYPE_CHECKING:
    from chess4d.board import Board4D


def bishop_moves(origin: Square4D, color: Color, board: "Board4D") -> Iterator[Move4D]:
    """Yield pseudo-legal bishop moves from ``origin`` for the given ``color``.

    "Pseudo-legal" means the moves respect the bishop's displacement and
    blocker/capture semantics (§3.7 Definition 6), but king-safety
    (§3.4 Definition 3) is *not* checked — that lives in the legality
    pipeline.

    The caller is responsible for ensuring ``origin`` actually holds a
    bishop of ``color``; this function does not re-verify that.
    """
    for ray in BISHOP_RAYS[origin]:
        for target in ray:
            occupant = board.occupant(target)
            if occupant is None:
                yield Move4D(from_sq=origin, to_sq=target)
                continue
            if occupant.color != color:
                yield Move4D(from_sq=origin, to_sq=target)
            break
