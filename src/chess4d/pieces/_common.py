"""Shared generators for sliding pieces (rook, bishop, queen).

Citations refer to Oana & Chiru, *A Mathematical Framework for
Four-Dimensional Chess*, MDPI AppliedMath 6(3):48, 2026
(DOI 10.3390/appliedmath6030048).

Sliders share one behavior: walk a precomputed ray, emitting targets
until an empty-board boundary, a friendly blocker (stop, no capture),
or an enemy blocker (emit a capture, then stop). Factoring that loop
here keeps rook, bishop, and queen generators to a single line each.

Leapers (knight, king) are a different shape — their natural form is
``for target in NEIGHBORS[origin]``, without the break-after-first-
blocker ceremony — and they are deliberately *not* routed through this
helper.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Iterator, Mapping

from chess4d.types import Color, Move4D, Square4D

if TYPE_CHECKING:
    from chess4d.board import Board4D


_RaysMap = Mapping[Square4D, tuple[tuple[Square4D, ...], ...]]


def slide_from(
    rays_map: _RaysMap, origin: Square4D, color: Color, board: "Board4D"
) -> Iterator[Move4D]:
    """Yield pseudo-legal slider moves from ``origin`` along every ray in ``rays_map``.

    "Pseudo-legal" means the generator respects displacement and
    blocker/capture semantics but does *not* check king-safety
    (paper §3.4 Definition 3) — that is the legality pipeline's concern.

    The caller is responsible for ensuring ``origin`` actually holds a
    piece of ``color`` whose geometry is ``rays_map``.
    """
    for ray in rays_map[origin]:
        for target in ray:
            occupant = board.occupant(target)
            if occupant is None:
                yield Move4D(from_sq=origin, to_sq=target)
                continue
            if occupant.color != color:
                yield Move4D(from_sq=origin, to_sq=target)
            # Whether friendly or enemy, the ray stops at the first blocker.
            break
