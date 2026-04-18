"""Knight-adjacency invariants (paper §3.8, Definition 8, Theorem 3).

Citations refer to Oana & Chiru, *A Mathematical Framework for
Four-Dimensional Chess*, MDPI AppliedMath 6(3):48, 2026
(DOI 10.3390/appliedmath6030048).

The knight is the first leaper: its displacement set is every
permutation of ``(±2, ±1, 0, 0)``, giving 48 directions, and interior
mobility is uniformly 48 (§3.8 Theorem 3). §3.8 Proposition 2(iii)
pins parity: a knight move's coordinate-sum delta is ``±2 ± 1``, which
is odd, so every knight move flips parity.

Closed-form mobility (§3.8 Theorem 3, 0-based form)::

    c_1(u) = [l(u) ≥ 1] + [r(u) ≥ 1]
    c_2(u) = [l(u) ≥ 2] + [r(u) ≥ 2]
    deg_N(p) = (Σ_i c_2(u_i)) · (Σ_i c_1(u_i)) − Σ_i c_2(u_i) · c_1(u_i)

with ``l(u) = u`` and ``r(u) = 7 − u``.
"""

from __future__ import annotations

import itertools

from chess4d import BOARD_SIZE, Square4D
from chess4d.geometry import KNIGHT_DISPLACEMENTS, KNIGHT_NEIGHBORS, KNIGHT_RAYS

from .conftest import all_squares


def _c1(u: int) -> int:
    return int(u >= 1) + int((BOARD_SIZE - 1 - u) >= 1)


def _c2(u: int) -> int:
    return int(u >= 2) + int((BOARD_SIZE - 1 - u) >= 2)


def _closed_form_knight_mobility(sq: Square4D) -> int:
    sum_c2 = sum(_c2(u) for u in sq)
    sum_c1 = sum(_c1(u) for u in sq)
    sum_c2_c1 = sum(_c2(u) * _c1(u) for u in sq)
    return sum_c2 * sum_c1 - sum_c2_c1


# --- KNIGHT_DISPLACEMENTS structural sanity ---------------------------------


def test_knight_displacements_count_is_48() -> None:
    """§3.8 Def 8: 4 axes for ±2 × 3 remaining axes for ±1 × 4 sign combos = 48."""
    assert len(KNIGHT_DISPLACEMENTS) == 48
    assert len(set(KNIGHT_DISPLACEMENTS)) == 48


def test_knight_displacements_shape() -> None:
    """Every displacement has one ±2, one ±1, and two zeros."""
    for d in KNIGHT_DISPLACEMENTS:
        sorted_abs = sorted(abs(v) for v in d)
        assert sorted_abs == [0, 0, 1, 2], d
        # sum of |v|: 3; two nonzero entries
        nonzero = [v for v in d if v != 0]
        assert len(nonzero) == 2


# --- KNIGHT_RAYS leaper shape -----------------------------------------------


def test_knight_rays_lockstep_with_displacements() -> None:
    """Each square has ``len(KNIGHT_DISPLACEMENTS)`` ray slots, lockstep."""
    for sq in all_squares():
        assert len(KNIGHT_RAYS[sq]) == len(KNIGHT_DISPLACEMENTS), sq


def test_knight_rays_each_has_length_zero_or_one() -> None:
    """Leaper rays are empty (out-of-bounds target) or single-element."""
    for sq in all_squares():
        for ray in KNIGHT_RAYS[sq]:
            assert len(ray) in (0, 1), (sq, ray)


def test_knight_rays_target_matches_displacement() -> None:
    """For every nonempty ray, the target equals ``origin + displacement``."""
    for sq in all_squares():
        for displacement, ray in zip(KNIGHT_DISPLACEMENTS, KNIGHT_RAYS[sq]):
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


# --- KNIGHT_NEIGHBORS and closed-form mobility ------------------------------


def test_knight_neighbors_flatten_nonempty_rays() -> None:
    """``KNIGHT_NEIGHBORS[sq]`` = union of single-element rays."""
    for sq in all_squares():
        expected = {target for ray in KNIGHT_RAYS[sq] for target in ray}
        assert KNIGHT_NEIGHBORS[sq] == frozenset(expected)


def test_knight_interior_mobility_is_48() -> None:
    """§3.8 Theorem 3: every square with all coords in [2, 5] has 48 knight neighbors."""
    for x, y, z, w in itertools.product(range(2, 6), repeat=4):
        sq = Square4D(x, y, z, w)
        assert len(KNIGHT_NEIGHBORS[sq]) == 48, sq


def test_knight_mobility_matches_closed_form_on_every_square() -> None:
    """§3.8 Thm 3 closed-form matches ``|KNIGHT_NEIGHBORS[sq]|`` on all 4096."""
    for sq in all_squares():
        assert len(KNIGHT_NEIGHBORS[sq]) == _closed_form_knight_mobility(sq), sq


def test_knight_corner_mobility_is_12() -> None:
    """(0,0,0,0): choose 1/4 axes for +2, 1/3 remaining for +1 (no negatives). 12."""
    assert len(KNIGHT_NEIGHBORS[Square4D(0, 0, 0, 0)]) == 12


# --- parity (§3.8 Proposition 2(iii)) ---------------------------------------


def test_knight_neighbors_always_flip_parity_on_every_square() -> None:
    """§3.8 Prop 2(iii): every knight neighbor differs in parity from the origin."""
    for sq in all_squares():
        origin_parity = sq.parity()
        for neighbor in KNIGHT_NEIGHBORS[sq]:
            assert neighbor.parity() != origin_parity, (sq, neighbor)
