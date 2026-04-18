"""Queen-adjacency invariants (paper §3.8, Definition 7).

Citations refer to Oana & Chiru, *A Mathematical Framework for
Four-Dimensional Chess*, MDPI AppliedMath 6(3):48, 2026
(DOI 10.3390/appliedmath6030048).

The queen's displacement set is the union of the rook's (1-axis) and
bishop's (2-axis) displacements. §3.8 Definition 7 explicitly restricts
the queen to those two classes: extending to 3- or 4-axis diagonals
would collapse rook/bishop/queen into a single piece class. Empty-board
mobility is the exact sum of rook and bishop mobility because the two
reach sets are always disjoint (Hamming-1 vs Hamming-2 neighbors).
"""

from __future__ import annotations

from chess4d import Square4D
from chess4d.geometry import (
    BISHOP_DIRECTIONS,
    BISHOP_NEIGHBORS,
    BISHOP_RAYS,
    QUEEN_DIRECTIONS,
    QUEEN_NEIGHBORS,
    QUEEN_RAYS,
    ROOK_DIRECTIONS,
    ROOK_NEIGHBORS,
    ROOK_RAYS,
)

from .conftest import all_squares


def _hamming_distance(a: Square4D, b: Square4D) -> int:
    return sum(int(ai != bi) for ai, bi in zip(a, b))


# --- QUEEN_DIRECTIONS structural sanity -------------------------------------


def test_queen_directions_count_is_32() -> None:
    """§3.8 Def 7: 8 rook directions + 24 bishop directions = 32 displacements."""
    assert len(QUEEN_DIRECTIONS) == 32
    assert len(set(QUEEN_DIRECTIONS)) == 32


def test_queen_directions_are_rook_then_bishop_in_order() -> None:
    """QUEEN_DIRECTIONS = ROOK_DIRECTIONS + BISHOP_DIRECTIONS (lockstep)."""
    assert tuple(QUEEN_DIRECTIONS) == tuple(ROOK_DIRECTIONS) + tuple(BISHOP_DIRECTIONS)


def test_queen_directions_hamming_weight_is_1_or_2() -> None:
    """§3.8 Def 7: every queen direction has exactly one or two nonzero entries."""
    for direction in QUEEN_DIRECTIONS:
        nonzero = sum(1 for v in direction if v != 0)
        assert nonzero in (1, 2), direction


# --- QUEEN_NEIGHBORS additivity ---------------------------------------------


def test_queen_neighbors_equal_rook_union_bishop_on_every_square() -> None:
    """§3.8 Def 7: queen reach = rook reach ∪ bishop reach, on all 4096 squares."""
    for sq in all_squares():
        assert QUEEN_NEIGHBORS[sq] == ROOK_NEIGHBORS[sq] | BISHOP_NEIGHBORS[sq], sq


def test_queen_rook_bishop_neighbors_are_disjoint_on_every_square() -> None:
    """Rook reach (Hamming-1) and bishop reach (Hamming-2) never overlap."""
    for sq in all_squares():
        assert ROOK_NEIGHBORS[sq].isdisjoint(BISHOP_NEIGHBORS[sq]), sq


def test_queen_mobility_equals_rook_plus_bishop_on_every_square() -> None:
    """Disjointness implies exact additivity of cardinalities."""
    for sq in all_squares():
        assert (
            len(QUEEN_NEIGHBORS[sq])
            == len(ROOK_NEIGHBORS[sq]) + len(BISHOP_NEIGHBORS[sq])
        ), sq


# --- corner / far-corner specific values ------------------------------------


def test_queen_corner_mobility_is_70() -> None:
    """(0,0,0,0): 28 rook + 42 bishop = 70."""
    assert len(QUEEN_NEIGHBORS[Square4D(0, 0, 0, 0)]) == 70


def test_queen_far_corner_mobility_is_70() -> None:
    """(7,7,7,7): by symmetry, 28 + 42 = 70."""
    assert len(QUEEN_NEIGHBORS[Square4D(7, 7, 7, 7)]) == 70


# --- Hamming-distance bound from Definition 7 -------------------------------


def test_queen_never_reaches_3_or_4_axis_targets() -> None:
    """§3.8 Def 7: queen is 1- and 2-axis only; Hamming distance ≤ 2."""
    for sq in all_squares():
        for neighbor in QUEEN_NEIGHBORS[sq]:
            assert _hamming_distance(sq, neighbor) in (1, 2), (sq, neighbor)


# --- QUEEN_RAYS structural sanity -------------------------------------------


def test_queen_rays_equal_rook_rays_then_bishop_rays() -> None:
    """QUEEN_RAYS[sq] = ROOK_RAYS[sq] + BISHOP_RAYS[sq] (lockstep with directions)."""
    for sq in all_squares():
        assert QUEEN_RAYS[sq] == ROOK_RAYS[sq] + BISHOP_RAYS[sq]


def test_queen_rays_count_is_32_per_square() -> None:
    """8 rook rays + 24 bishop rays = 32 per square (empty tuples allowed at boundary)."""
    for sq in all_squares():
        assert len(QUEEN_RAYS[sq]) == 32, sq


def test_queen_rays_are_ordered_by_distance() -> None:
    """``QUEEN_RAYS[sq][k]`` steps outward along ``QUEEN_DIRECTIONS[k]``."""
    for sq in all_squares():
        for direction, ray in zip(QUEEN_DIRECTIONS, QUEEN_RAYS[sq]):
            for step, target in enumerate(ray, start=1):
                expected = Square4D(
                    sq.x + step * direction[0],
                    sq.y + step * direction[1],
                    sq.z + step * direction[2],
                    sq.w + step * direction[3],
                )
                assert target == expected
