"""Rook-adjacency invariants (paper §3.5).

Citations refer to Oana & Chiru, *A Mathematical Framework for
Four-Dimensional Chess*, MDPI AppliedMath 6(3):48, 2026
(DOI 10.3390/appliedmath6030048).

The rook-move graph on ``B = {0,…,7}^4`` is the Hamming graph
``H(4, 8) ≅ K_8 □ K_8 □ K_8 □ K_8`` (Theorem 2). These tests verify:

* Corollary 1 — every square has exactly 28 empty-board rook neighbors.
* Theorem 1 (per-direction) — the ray along ``+e_x`` from ``(x,…)`` has
  length ``7 − x``; the ray along ``−e_x`` has length ``x``; analogously
  for the other three axes.
* Theorem 2 (adjacency) — two squares are empty-board rook-adjacent iff
  they differ in exactly one coordinate.
* Theorem 2 (diameter) — BFS from any square reaches every square in at
  most 4 steps.
"""

from __future__ import annotations

from collections import deque

from chess4d import BOARD_SIZE, Square4D
from chess4d.geometry import ROOK_DIRECTIONS, ROOK_NEIGHBORS, ROOK_RAYS

from .conftest import all_squares


def _coords_differing(a: Square4D, b: Square4D) -> int:
    return sum(int(ai != bi) for ai, bi in zip(a, b))


# --- Corollary 1: 28-regular ------------------------------------------------


def test_rook_mobility_is_28_on_every_square() -> None:
    """Paper §3.5, Corollary 1: empty-board rook mobility ≡ 28."""
    for sq in all_squares():
        assert len(ROOK_NEIGHBORS[sq]) == 28, sq


# --- Theorem 1: per-direction ray length ------------------------------------


def test_rook_per_direction_ray_length_matches_theorem_1() -> None:
    """Theorem 1: axis-aligned ray length equals distance to boundary."""
    for sq in all_squares():
        rays = ROOK_RAYS[sq]
        # Direction order is lockstep with ROOK_DIRECTIONS.
        assert len(rays[0]) == BOARD_SIZE - 1 - sq.x   # +x
        assert len(rays[1]) == sq.x                    # -x
        assert len(rays[2]) == BOARD_SIZE - 1 - sq.y   # +y
        assert len(rays[3]) == sq.y                    # -y
        assert len(rays[4]) == BOARD_SIZE - 1 - sq.z   # +z
        assert len(rays[5]) == sq.z                    # -z
        assert len(rays[6]) == BOARD_SIZE - 1 - sq.w   # +w
        assert len(rays[7]) == sq.w                    # -w


def test_rook_total_mobility_matches_theorem_1_formula() -> None:
    """Theorem 1: ``M_R(p) = sum over axes of (c_i) + (7 − c_i)`` (0-based)."""
    for sq in all_squares():
        expected = sq.x + (BOARD_SIZE - 1 - sq.x) \
                 + sq.y + (BOARD_SIZE - 1 - sq.y) \
                 + sq.z + (BOARD_SIZE - 1 - sq.z) \
                 + sq.w + (BOARD_SIZE - 1 - sq.w)
        assert expected == 28  # Corollary 1: always 28.
        assert len(ROOK_NEIGHBORS[sq]) == expected


# --- Theorem 2: Hamming adjacency ------------------------------------------


def test_rook_adjacency_is_single_coordinate_difference() -> None:
    """Theorem 2: ``v`` and ``w`` are rook-adjacent iff Hamming distance = 1."""
    for sq in all_squares():
        neighbors = ROOK_NEIGHBORS[sq]
        # Every neighbor differs in exactly one coordinate.
        for n in neighbors:
            assert _coords_differing(sq, n) == 1, (sq, n)
        # Every square differing in exactly one coordinate is a neighbor.
        # (Sampled by construction: iterate all such squares and check membership.)
        for axis in range(4):
            for value in range(BOARD_SIZE):
                if value == sq[axis]:
                    continue
                target = list(sq)
                target[axis] = value
                assert Square4D(*target) in neighbors


def test_rook_directions_are_axis_unit_vectors() -> None:
    """Every direction is a unit vector along exactly one axis."""
    assert len(ROOK_DIRECTIONS) == 8
    for direction in ROOK_DIRECTIONS:
        nonzero = [d for d in direction if d != 0]
        assert len(nonzero) == 1
        assert nonzero[0] in (-1, +1)


# --- Theorem 2: diameter ----------------------------------------------------


def _bfs_eccentricity(source: Square4D) -> int:
    distances: dict[Square4D, int] = {source: 0}
    queue: deque[Square4D] = deque([source])
    while queue:
        cur = queue.popleft()
        for neighbor in ROOK_NEIGHBORS[cur]:
            if neighbor not in distances:
                distances[neighbor] = distances[cur] + 1
                queue.append(neighbor)
    # Every square must be reachable (the graph is connected).
    assert len(distances) == BOARD_SIZE ** 4
    return max(distances.values())


def test_rook_diameter_from_origin_is_four() -> None:
    """Theorem 2: ``diam H(4, 8) = 4``; BFS from ``(0,0,0,0)`` confirms it."""
    assert _bfs_eccentricity(Square4D(0, 0, 0, 0)) == 4


def test_rook_diameter_from_opposite_corner_is_four() -> None:
    """The opposite corner must also be 4-eccentric (graph is vertex-transitive)."""
    assert _bfs_eccentricity(Square4D(7, 7, 7, 7)) == 4


def test_rook_diameter_from_interior_square_is_four() -> None:
    """Interior squares reach everything within 4 steps too."""
    assert _bfs_eccentricity(Square4D(3, 4, 5, 2)) == 4


# --- Ray ordering -----------------------------------------------------------


def test_rook_rays_are_ordered_by_distance() -> None:
    """Each ray lists squares in order from nearest to farthest."""
    for sq in all_squares():
        for direction, ray in zip(ROOK_DIRECTIONS, ROOK_RAYS[sq]):
            for step, target in enumerate(ray, start=1):
                expected = Square4D(
                    sq.x + step * direction[0],
                    sq.y + step * direction[1],
                    sq.z + step * direction[2],
                    sq.w + step * direction[3],
                )
                assert target == expected
