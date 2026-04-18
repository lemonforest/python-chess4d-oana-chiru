"""Precomputed geometry for 4D move generation.

Citations refer to Oana & Chiru, *A Mathematical Framework for
Four-Dimensional Chess*, MDPI AppliedMath 6(3):48, 2026
(DOI 10.3390/appliedmath6030048).

Rook geometry (§3.5)
--------------------
Axis-aligned displacements ``±e_i`` for ``i ∈ {x, y, z, w}``; the rook
slides along one of the eight directions, stopping at the board
boundary or a blocker. §3.5 Corollary 1 guarantees uniform empty-board
mobility 28; the graph is the Hamming graph ``H(4, 8)`` (§3.5 Thm 2).

Bishop geometry (§3.7)
----------------------
A bishop displacement changes exactly two coordinates by equal absolute
value (§3.7 Definition 6). There are six coordinate planes (§3.7 Lemma
5) — ``XY, XZ, XW, YZ, YW, ZW`` — and four sign combinations per plane,
for 24 rays per square. Parity ``(x+y+z+w) mod 2`` is preserved by
every bishop move (§3.7 Lemma 2), so the bishop graph has exactly two
connected components (§3.7 Theorem 4).

Queen geometry (§3.8 Definition 7)
----------------------------------
The queen's displacement set is the **union** of the rook's (1-axis)
and the bishop's (2-axis). It is deliberately restricted to those two
classes; 3- or 4-axis diagonals are not queen moves (§3.8 Def 7). The
queen ray table is the per-square concatenation of the rook and bishop
rays, lockstep with :data:`QUEEN_DIRECTIONS`.

Knight geometry (§3.8 Definition 8, Theorem 3)
----------------------------------------------
The knight is a leaper: its 48 displacements are all permutations of
``(±2, ±1, 0, 0)``. Intermediate squares do not exist — the knight
"jumps." To keep the dispatch-table uniform with sliders, each knight
ray is modeled as a length-0-or-1 tuple (0 when the target is out of
bounds, 1 when it is in bounds). Empty-board mobility follows the §3.8
Theorem 3 stratification formula.

King geometry (§3.9 Definition 9)
---------------------------------
The king is a Chebyshev-1 leaper: its 80 displacements are every
nonzero vector in ``{−1, 0, +1}^4``. Same leaper shape as the knight
(length-0-or-1 rays); interior mobility 80 (§3.2 Lemma 1). Castling
(§3.9 Definition 10) requires castling-rights state and is not
implemented here.

Ordering conventions (load-bearing for tests)
---------------------------------------------
* :data:`ROOK_DIRECTIONS` / :data:`ROOK_RAYS` are indexed in lockstep.
* :data:`BISHOP_PLANES` follows ``itertools.combinations(range(4), 2)``.
* :data:`BISHOP_DIRECTIONS` iterates plane-outer, sign-inner, with sign
  order ``(+,+), (+,-), (-,+), (-,-)`` matching the paper's
  ``d_{++}, d_{+-}, d_{-+}, d_{--}`` (§3.8 closed-form mobility).
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


# --- bishop -----------------------------------------------------------------


BISHOP_PLANES: Tuple[Tuple[int, int], ...] = tuple(itertools.combinations(range(4), 2))
"""The six coordinate planes (§3.7 Lemma 5), as axis-index pairs.

Order: ``(0,1) XY, (0,2) XZ, (0,3) XW, (1,2) YZ, (1,3) YW, (2,3) ZW`` —
lexicographic on ``itertools.combinations(range(4), 2)``.
"""


def _make_bishop_direction(plane: Tuple[int, int], signs: Tuple[int, int]) -> Displacement:
    vec = [0, 0, 0, 0]
    vec[plane[0]] = signs[0]
    vec[plane[1]] = signs[1]
    return (vec[0], vec[1], vec[2], vec[3])


_BISHOP_SIGNS: Tuple[Tuple[int, int], ...] = ((+1, +1), (+1, -1), (-1, +1), (-1, -1))
"""Sign order within each plane, matching the paper's ``d_{++}, d_{+-},
d_{-+}, d_{--}`` notation (§3.8 closed-form mobility)."""


BISHOP_DIRECTIONS: Tuple[Displacement, ...] = tuple(
    _make_bishop_direction(plane, signs)
    for plane in BISHOP_PLANES
    for signs in _BISHOP_SIGNS
)
"""The 24 bishop displacements (6 planes × 4 sign combinations).

Ordered plane-outer, sign-inner. For direction index ``k``,
``(plane_idx, sign_idx) = divmod(k, 4)``.
"""


def _build_bishop_rays() -> dict[Square4D, tuple[tuple[Square4D, ...], ...]]:
    return {
        Square4D(x, y, z, w): tuple(
            _ray_from(Square4D(x, y, z, w), direction) for direction in BISHOP_DIRECTIONS
        )
        for x, y, z, w in itertools.product(range(BOARD_SIZE), repeat=4)
    }


BISHOP_RAYS: Mapping[Square4D, tuple[tuple[Square4D, ...], ...]] = _build_bishop_rays()
"""Per-square ordered bishop rays, indexed in lockstep with :data:`BISHOP_DIRECTIONS`.

``BISHOP_RAYS[sq][k]`` is the ordered list of squares hit stepping from
``sq`` along ``BISHOP_DIRECTIONS[k]`` (nearest to farthest, origin
excluded).
"""


BISHOP_NEIGHBORS: Mapping[Square4D, frozenset[Square4D]] = {
    sq: frozenset(t for ray in rays for t in ray) for sq, rays in BISHOP_RAYS.items()
}
"""Empty-board bishop reach from every square (paper §3.7–§3.8).

Per §3.7 Lemma 2, every element of ``BISHOP_NEIGHBORS[sq]`` shares
parity with ``sq``; per §3.7 Theorem 4, the graph has exactly two
connected components of size ``8^4 / 2 = 2048`` each.
"""


# --- queen ------------------------------------------------------------------


QUEEN_DIRECTIONS: Tuple[Displacement, ...] = ROOK_DIRECTIONS + BISHOP_DIRECTIONS
"""The 32 queen displacements (paper §3.8 Definition 7).

Concatenation of :data:`ROOK_DIRECTIONS` (8 axis-unit vectors) and
:data:`BISHOP_DIRECTIONS` (24 planar-diagonal vectors). **Do not** add
3- or 4-axis diagonals: §3.8 Def 7 restricts the queen to 1- and 2-axis
moves, and extending it would collapse rook/bishop/queen into a single
piece class.
"""


QUEEN_RAYS: Mapping[Square4D, tuple[tuple[Square4D, ...], ...]] = {
    sq: ROOK_RAYS[sq] + BISHOP_RAYS[sq] for sq in ROOK_RAYS
}
"""Per-square queen rays, lockstep with :data:`QUEEN_DIRECTIONS`.

``QUEEN_RAYS[sq][k]`` is the ordered list of squares hit from ``sq``
along ``QUEEN_DIRECTIONS[k]``: axis rays for ``k < 8`` and planar-
diagonal rays for ``8 ≤ k < 32``.
"""


QUEEN_NEIGHBORS: Mapping[Square4D, frozenset[Square4D]] = {
    sq: ROOK_NEIGHBORS[sq] | BISHOP_NEIGHBORS[sq] for sq in ROOK_NEIGHBORS
}
"""Empty-board queen reach from every square (paper §3.8 Def 7).

The rook and bishop reach sets are always disjoint (Hamming-1 vs
Hamming-2 neighbors), so ``|QUEEN_NEIGHBORS[sq]|`` equals
``|ROOK_NEIGHBORS[sq]| + |BISHOP_NEIGHBORS[sq]|`` exactly.
"""


# --- knight -----------------------------------------------------------------


def _build_knight_displacements() -> Tuple[Displacement, ...]:
    """All 48 permutations of ``(±2, ±1, 0, 0)`` (paper §3.8 Def 8).

    Deterministic order: outer loop over ordered pairs ``(i, j)`` of
    distinct axes (``i`` = axis for ±2, ``j`` = axis for ±1); inner loop
    over sign combinations ``((+2,+1), (+2,-1), (-2,+1), (-2,-1))``.
    12 ordered axis pairs × 4 sign combinations = 48.
    """
    result: list[Displacement] = []
    for i in range(4):
        for j in range(4):
            if i == j:
                continue
            for s2, s1 in ((+2, +1), (+2, -1), (-2, +1), (-2, -1)):
                vec = [0, 0, 0, 0]
                vec[i] = s2
                vec[j] = s1
                result.append((vec[0], vec[1], vec[2], vec[3]))
    return tuple(result)


KNIGHT_DISPLACEMENTS: Tuple[Displacement, ...] = _build_knight_displacements()
"""The 48 knight displacements (paper §3.8 Definition 8, Theorem 3).

Each entry is a permutation of ``(±2, ±1, 0, 0)``: one axis carries
``±2``, a different axis carries ``±1``, the remaining two are zero.
"""


def _leaper_ray(origin: Square4D, displacement: Displacement) -> tuple[Square4D, ...]:
    """One-step leaper "ray": a single-element tuple if in bounds, else empty.

    Uniform shape with slider rays lets :meth:`Board4D._walk_ray_or_raise`
    handle leapers without special-casing (there are simply no
    intermediate squares to scan).
    """
    target = Square4D(
        origin.x + displacement[0],
        origin.y + displacement[1],
        origin.z + displacement[2],
        origin.w + displacement[3],
    )
    return (target,) if target.in_bounds() else ()


def _build_knight_rays() -> dict[Square4D, tuple[tuple[Square4D, ...], ...]]:
    return {
        Square4D(x, y, z, w): tuple(
            _leaper_ray(Square4D(x, y, z, w), d) for d in KNIGHT_DISPLACEMENTS
        )
        for x, y, z, w in itertools.product(range(BOARD_SIZE), repeat=4)
    }


KNIGHT_RAYS: Mapping[Square4D, tuple[tuple[Square4D, ...], ...]] = _build_knight_rays()
"""Per-square knight rays, lockstep with :data:`KNIGHT_DISPLACEMENTS`.

Leaper shape: each ray is either empty (target out of bounds) or a
one-element tuple containing the single jump target. Intermediate
squares do not exist, so ray-walk validation in
:meth:`Board4D._walk_ray_or_raise` no-ops for knight moves.
"""


KNIGHT_NEIGHBORS: Mapping[Square4D, frozenset[Square4D]] = {
    sq: frozenset(t for ray in rays for t in ray) for sq, rays in KNIGHT_RAYS.items()
}
"""Empty-board knight reach from every square (paper §3.8 Theorem 3).

Interior mobility is uniformly 48 on ``{2,…,5}^4``; boundary-clipped
elsewhere by the §3.8 Theorem 3 closed-form stratification.
"""


# --- king -------------------------------------------------------------------


KING_DISPLACEMENTS: Tuple[Displacement, ...] = tuple(
    (dx, dy, dz, dw)
    for dx, dy, dz, dw in itertools.product((-1, 0, +1), repeat=4)
    if (dx, dy, dz, dw) != (0, 0, 0, 0)
)
"""The 80 king displacements (paper §3.9 Definition 9).

All nonzero vectors in ``{−1, 0, +1}^4`` in lexicographic order (the
zero tuple is excluded). ``3^4 − 1 = 80`` (§3.2 Lemma 1).
"""


def _build_king_rays() -> dict[Square4D, tuple[tuple[Square4D, ...], ...]]:
    return {
        Square4D(x, y, z, w): tuple(
            _leaper_ray(Square4D(x, y, z, w), d) for d in KING_DISPLACEMENTS
        )
        for x, y, z, w in itertools.product(range(BOARD_SIZE), repeat=4)
    }


KING_RAYS: Mapping[Square4D, tuple[tuple[Square4D, ...], ...]] = _build_king_rays()
"""Per-square king rays, lockstep with :data:`KING_DISPLACEMENTS`.

Same leaper shape as :data:`KNIGHT_RAYS`: each ray is empty (target
out of bounds) or a one-element tuple (target in bounds).
"""


KING_NEIGHBORS: Mapping[Square4D, frozenset[Square4D]] = {
    sq: frozenset(t for ray in rays for t in ray) for sq, rays in KING_RAYS.items()
}
"""Empty-board king reach — exactly the Chebyshev-1 ball (§3.9 Def 9).

``KING_NEIGHBORS[sq] == {q ∈ B : d∞(sq, q) == 1}``. Interior mobility
is uniformly 80 (§3.2 Lemma 1); of those 80, exactly 40 preserve
parity and 40 flip it (§3.8 Prop 2(iv)).
"""
