"""King-adjacency invariants (paper §3.9, Definition 9; §3.2, Lemma 1).

Citations refer to Oana & Chiru, *A Mathematical Framework for
Four-Dimensional Chess*, MDPI AppliedMath 6(3):48, 2026
(DOI 10.3390/appliedmath6030048).

The king is a Chebyshev-1 leaper: it moves to any square at ``d∞ = 1``.
Its 80 displacements are the nonzero vectors in ``{−1, 0, +1}^4``;
interior mobility is uniformly 80 (§3.2 Lemma 1). The 80 king
displacements split evenly by parity: 40 preserve ``π`` (even number of
nonzero components — Hamming 2 or 4) and 40 flip it (odd — Hamming 1
or 3). §3.8 Proposition 2(iv).
"""

from __future__ import annotations

import itertools

from chess4d import BOARD_SIZE, Square4D
from chess4d.geometry import KING_DISPLACEMENTS, KING_NEIGHBORS, KING_RAYS

from .conftest import all_squares


# --- KING_DISPLACEMENTS structural sanity -----------------------------------


def test_king_displacements_count_is_80() -> None:
    """3^4 − 1 = 80: all nonzero vectors in {−1, 0, +1}^4."""
    assert len(KING_DISPLACEMENTS) == 80
    assert len(set(KING_DISPLACEMENTS)) == 80


def test_king_displacements_values_in_minus_one_zero_plus_one() -> None:
    for d in KING_DISPLACEMENTS:
        for v in d:
            assert v in (-1, 0, +1), d
        assert d != (0, 0, 0, 0)


def test_king_displacements_are_lexicographic() -> None:
    """Deterministic order: lex on itertools.product, zero tuple removed."""
    expected = tuple(
        d for d in itertools.product((-1, 0, +1), repeat=4) if d != (0, 0, 0, 0)
    )
    assert tuple(KING_DISPLACEMENTS) == expected


# --- KING_RAYS leaper shape -------------------------------------------------


def test_king_rays_lockstep_with_displacements() -> None:
    for sq in all_squares():
        assert len(KING_RAYS[sq]) == len(KING_DISPLACEMENTS), sq


def test_king_rays_each_has_length_zero_or_one() -> None:
    for sq in all_squares():
        for ray in KING_RAYS[sq]:
            assert len(ray) in (0, 1), (sq, ray)


def test_king_rays_target_matches_displacement() -> None:
    for sq in all_squares():
        for displacement, ray in zip(KING_DISPLACEMENTS, KING_RAYS[sq]):
            if not ray:
                continue
            (target,) = ray
            expected = Square4D(
                sq.x + displacement[0],
                sq.y + displacement[1],
                sq.z + displacement[2],
                sq.w + displacement[3],
            )
            assert target == expected


# --- KING_NEIGHBORS equals Chebyshev-1 ---------------------------------------


def test_king_neighbors_equal_chebyshev_1_set_on_every_square() -> None:
    """§3.9 Def 9: ``KING_NEIGHBORS[sq] == {q ∈ B : d∞(sq, q) == 1}``."""
    for sq in all_squares():
        expected = set()
        for dx, dy, dz, dw in itertools.product((-1, 0, +1), repeat=4):
            if (dx, dy, dz, dw) == (0, 0, 0, 0):
                continue
            target = Square4D(sq.x + dx, sq.y + dy, sq.z + dz, sq.w + dw)
            if target.in_bounds():
                expected.add(target)
        assert KING_NEIGHBORS[sq] == frozenset(expected), sq


def test_king_interior_mobility_is_80() -> None:
    """§3.2 Lemma 1: interior king (coords in [1, 6]) has 80 neighbors."""
    for x, y, z, w in itertools.product(range(1, BOARD_SIZE - 1), repeat=4):
        sq = Square4D(x, y, z, w)
        assert len(KING_NEIGHBORS[sq]) == 80, sq


def test_king_corner_mobility_is_15() -> None:
    """(0,0,0,0): all (0/+1)-per-axis tuples except the self. 2^4 − 1 = 15."""
    assert len(KING_NEIGHBORS[Square4D(0, 0, 0, 0)]) == 15


# --- parity split (§3.8 Prop 2(iv)) -----------------------------------------


def test_king_parity_split_is_40_40_for_interior_squares() -> None:
    """Interior king: exactly 40 neighbors preserve parity, 40 flip it."""
    origin = Square4D(3, 3, 3, 3)
    preserve = sum(1 for n in KING_NEIGHBORS[origin] if n.parity() == origin.parity())
    flip = sum(1 for n in KING_NEIGHBORS[origin] if n.parity() != origin.parity())
    assert preserve == 40
    assert flip == 40
