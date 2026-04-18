"""Bishop-adjacency invariants (paper §3.7, §3.8).

Citations refer to Oana & Chiru, *A Mathematical Framework for
Four-Dimensional Chess*, MDPI AppliedMath 6(3):48, 2026
(DOI 10.3390/appliedmath6030048).

The bishop graph on ``B = {0,…,7}^4`` has:

* 6 coordinate planes (§3.7 Lemma 5) — XY, XZ, XW, YZ, YW, ZW.
* Each square's 24 rays (6 planes × 4 sign combinations) reach only
  same-parity squares (§3.7 Lemma 2; §3.8 Prop 2(ii)).
* The graph has exactly two connected components, one per parity
  class (§3.7 Theorem 4).
* Empty-board mobility is the §3.8 closed-form sum of 24 diagonal
  boundary-distances.
"""

from __future__ import annotations

import itertools
from collections import deque

from chess4d import BOARD_SIZE, Square4D
from chess4d.geometry import (
    BISHOP_DIRECTIONS,
    BISHOP_NEIGHBORS,
    BISHOP_PLANES,
    BISHOP_RAYS,
)

from .conftest import all_squares


def _closed_form_bishop_mobility(sq: Square4D) -> int:
    """Paper §3.8 closed-form: sum over 6 planes of four diagonal distances."""
    total = 0
    for i, j in BISHOP_PLANES:
        c_i, c_j = sq[i], sq[j]
        up_i = BOARD_SIZE - 1 - c_i
        up_j = BOARD_SIZE - 1 - c_j
        d_pp = min(up_i, up_j)
        d_pm = min(up_i, c_j)
        d_mp = min(c_i, up_j)
        d_mm = min(c_i, c_j)
        total += d_pp + d_pm + d_mp + d_mm
    return total


# --- BISHOP_DIRECTIONS + BISHOP_PLANES structural sanity --------------------


def test_bishop_planes_are_the_six_axis_pairs() -> None:
    """§3.7 Lemma 5: exactly the six distinct coordinate pairs."""
    assert len(BISHOP_PLANES) == 6
    assert len(set(BISHOP_PLANES)) == 6
    expected = tuple(itertools.combinations(range(4), 2))
    assert tuple(BISHOP_PLANES) == expected


def test_bishop_directions_count_is_24() -> None:
    """6 planes × 4 sign combinations = 24 directions."""
    assert len(BISHOP_DIRECTIONS) == 24
    assert len(set(BISHOP_DIRECTIONS)) == 24


def test_bishop_directions_match_definition_6_shape() -> None:
    """§3.7 Definition 6: each direction has exactly two nonzero ±1 entries."""
    for direction in BISHOP_DIRECTIONS:
        nonzero_positions = [i for i, v in enumerate(direction) if v != 0]
        assert len(nonzero_positions) == 2
        for pos in nonzero_positions:
            assert direction[pos] in (-1, +1)
        # The two nonzero positions match one of the six planes.
        assert tuple(nonzero_positions) in BISHOP_PLANES


# --- closed-form mobility (§3.8) --------------------------------------------


def test_bishop_mobility_matches_closed_form_on_every_square() -> None:
    """Per-square: ``|BISHOP_NEIGHBORS[sq]| == Σ d_±±`` over 6 planes (§3.8)."""
    for sq in all_squares():
        assert len(BISHOP_NEIGHBORS[sq]) == _closed_form_bishop_mobility(sq), sq


def test_bishop_corner_mobility_is_42() -> None:
    """(0,0,0,0): only the ++ diagonal works in each plane, length 7. 6 × 7 = 42."""
    assert len(BISHOP_NEIGHBORS[Square4D(0, 0, 0, 0)]) == 42


def test_bishop_far_corner_mobility_is_42() -> None:
    """(7,7,7,7): by symmetry, only the -- diagonal works per plane. 6 × 7 = 42."""
    assert len(BISHOP_NEIGHBORS[Square4D(7, 7, 7, 7)]) == 42


# --- interior structure (§3.7 Lemma 3) --------------------------------------


def test_bishop_interior_rays_have_length_at_least_two() -> None:
    """§3.7 Lemma 3: in 0-based ``{2,3,4,5}^4``, every ray has ≥ 2 squares."""
    for x, y, z, w in itertools.product(range(2, 6), repeat=4):
        sq = Square4D(x, y, z, w)
        for ray in BISHOP_RAYS[sq]:
            assert len(ray) >= 2, (sq, ray)


# --- parity (§3.7 Lemma 2, Theorem 4; §3.8 Prop 2(ii)) ----------------------


def test_bishop_neighbors_preserve_parity_on_every_square() -> None:
    """§3.7 Lemma 2: every bishop neighbor shares parity with the origin."""
    for sq in all_squares():
        origin_parity = sq.parity()
        for neighbor in BISHOP_NEIGHBORS[sq]:
            assert neighbor.parity() == origin_parity, (sq, neighbor)


def _bfs_component(source: Square4D) -> set[Square4D]:
    seen = {source}
    queue: deque[Square4D] = deque([source])
    while queue:
        cur = queue.popleft()
        for neighbor in BISHOP_NEIGHBORS[cur]:
            if neighbor not in seen:
                seen.add(neighbor)
                queue.append(neighbor)
    return seen


def test_bishop_bfs_from_even_origin_reaches_2048_squares_all_parity_zero() -> None:
    """§3.7 Theorem 4: the even-parity component has size ``8^4 / 2 = 2048``."""
    component = _bfs_component(Square4D(0, 0, 0, 0))
    assert len(component) == (BOARD_SIZE ** 4) // 2
    assert all(sq.parity() == 0 for sq in component)


def test_bishop_bfs_from_odd_origin_reaches_2048_squares_all_parity_one() -> None:
    """§3.7 Theorem 4: the odd-parity component has size ``8^4 / 2 = 2048``."""
    component = _bfs_component(Square4D(1, 0, 0, 0))
    assert len(component) == (BOARD_SIZE ** 4) // 2
    assert all(sq.parity() == 1 for sq in component)


def test_bishop_parity_components_are_disjoint_and_cover_board() -> None:
    """§3.7 Theorem 4: the two components partition B exactly."""
    even = _bfs_component(Square4D(0, 0, 0, 0))
    odd = _bfs_component(Square4D(1, 0, 0, 0))
    assert even.isdisjoint(odd)
    assert even | odd == set(all_squares())


# --- ray ordering (engine-design invariant) ---------------------------------


def test_bishop_rays_are_ordered_by_distance() -> None:
    """``BISHOP_RAYS[sq][k]`` = squares stepping along ``BISHOP_DIRECTIONS[k]``."""
    for sq in all_squares():
        for direction, ray in zip(BISHOP_DIRECTIONS, BISHOP_RAYS[sq]):
            for step, target in enumerate(ray, start=1):
                expected = Square4D(
                    sq.x + step * direction[0],
                    sq.y + step * direction[1],
                    sq.z + step * direction[2],
                    sq.w + step * direction[3],
                )
                assert target == expected
