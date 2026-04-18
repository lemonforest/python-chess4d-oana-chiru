"""Precomputed geometry for 4D move generation.

Citations refer to Oana & Chiru, *A Mathematical Framework for
Four-Dimensional Chess*, MDPI AppliedMath 6(3):48, 2026
(DOI 10.3390/appliedmath6030048).

The paper's displacement model for the rook (§3.5) is axis-aligned: the
rook moves along one of the eight axis-unit directions ``±e_i`` for
``i ∈ {x, y, z, w}``, stopping at the board boundary or a blocker. This
module precomputes, once at import time:

* :data:`ROOK_DIRECTIONS` — the eight unit displacements.
* :data:`ROOK_RAYS` — for every square, an 8-tuple (one per direction)
  of the squares encountered along that ray, in order from nearest to
  farthest. Order matters: move generation walks each ray and stops at
  the first blocker.
* :data:`ROOK_NEIGHBORS` — for every square, the flat frozenset of
  every empty-board reachable target (the union of the eight rays).

The paper is silent on whether to cache adjacency (this is engine-design
territory), but §3.5, Corollary 1 guarantees ``|ROOK_NEIGHBORS[sq]| =
28`` for every square, and the adjacency matches the Hamming graph
``H(4, 8)`` (§3.5, Theorem 2).
"""

from __future__ import annotations

import itertools
from typing import Mapping, Tuple

from chess4d.types import BOARD_SIZE, Square4D

Displacement = Tuple[int, int, int, int]

ROOK_DIRECTIONS: Tuple[Displacement, ...] = (
    (+1, 0, 0, 0), (-1, 0, 0, 0),
    (0, +1, 0, 0), (0, -1, 0, 0),
    (0, 0, +1, 0), (0, 0, -1, 0),
    (0, 0, 0, +1), (0, 0, 0, -1),
)
"""The eight axis-unit displacements ``±e_i`` (paper §3.5)."""


def _ray_from(origin: Square4D, direction: Displacement) -> Tuple[Square4D, ...]:
    """Ray-march from ``origin`` along ``direction`` until leaving the board.

    Yields squares in order from nearest to farthest (distance 1, 2, …).
    The origin itself is excluded.
    """
    ray: list[Square4D] = []
    x, y, z, w = origin
    dx, dy, dz, dw = direction
    step = 1
    while True:
        target = Square4D(x + step * dx, y + step * dy, z + step * dz, w + step * dw)
        if not target.in_bounds():
            break
        ray.append(target)
        step += 1
    return tuple(ray)


def _build_rook_rays() -> dict[Square4D, tuple[tuple[Square4D, ...], ...]]:
    return {
        Square4D(x, y, z, w): tuple(
            _ray_from(Square4D(x, y, z, w), direction) for direction in ROOK_DIRECTIONS
        )
        for x, y, z, w in itertools.product(range(BOARD_SIZE), repeat=4)
    }


ROOK_RAYS: Mapping[Square4D, tuple[tuple[Square4D, ...], ...]] = _build_rook_rays()
"""Per-square ordered rays, one tuple per entry in :data:`ROOK_DIRECTIONS`.

Indexed in lockstep with ``ROOK_DIRECTIONS``: ``ROOK_RAYS[sq][k]`` is the
ordered list of squares hit when stepping from ``sq`` along
``ROOK_DIRECTIONS[k]``. Used by blocker-aware move generation.
"""


ROOK_NEIGHBORS: Mapping[Square4D, frozenset[Square4D]] = {
    sq: frozenset(t for ray in rays for t in ray) for sq, rays in ROOK_RAYS.items()
}
"""Empty-board rook reach from every square (paper §3.5, Corollary 1).

``|ROOK_NEIGHBORS[sq]| == 28`` uniformly for every ``sq ∈ B``; the
associated graph is the Hamming graph ``H(4, 8)`` (§3.5, Theorem 2).
"""
