"""Tests for :class:`Square4D` primitives.

Citations refer to Oana & Chiru, *A Mathematical Framework for
Four-Dimensional Chess*, MDPI AppliedMath 6(3):48, 2026
(DOI 10.3390/appliedmath6030048).
"""

from __future__ import annotations

from hypothesis import given

from chess4d import BOARD_SIZE, Square4D

from .conftest import squares_strategy


# --- in_bounds ---------------------------------------------------------------


def test_square_in_bounds_origin_is_true() -> None:
    """Paper §3.1: ``(0,0,0,0)`` is the 0-based corner of ``B``."""
    assert Square4D(0, 0, 0, 0).in_bounds() is True


def test_square_in_bounds_far_corner_is_true() -> None:
    """Paper §3.1: the opposite corner ``(7,7,7,7)`` also lies in ``B``."""
    assert Square4D(BOARD_SIZE - 1, BOARD_SIZE - 1, BOARD_SIZE - 1, BOARD_SIZE - 1).in_bounds() is True


def test_square_in_bounds_negative_coord_is_false() -> None:
    assert Square4D(-1, 0, 0, 0).in_bounds() is False


def test_square_in_bounds_coord_equal_to_size_is_false() -> None:
    """Upper bound is exclusive: ``BOARD_SIZE`` itself is out of range."""
    assert Square4D(0, 0, 0, BOARD_SIZE).in_bounds() is False


def test_square_in_bounds_each_axis_independently() -> None:
    """A single out-of-range coordinate on any axis disqualifies the square."""
    for axis in range(4):
        coords = [0, 0, 0, 0]
        coords[axis] = BOARD_SIZE
        assert Square4D(*coords).in_bounds() is False


# --- parity ------------------------------------------------------------------


def test_parity_origin_is_zero() -> None:
    """Paper §3.7, Lemma 2: ``π(0,0,0,0) = 0``."""
    assert Square4D(0, 0, 0, 0).parity() == 0


def test_parity_unit_step_is_one() -> None:
    """A single unit step flips parity (§3.7, Lemma 2)."""
    assert Square4D(1, 0, 0, 0).parity() == 1
    assert Square4D(0, 1, 0, 0).parity() == 1
    assert Square4D(0, 0, 1, 0).parity() == 1
    assert Square4D(0, 0, 0, 1).parity() == 1


def test_parity_all_ones_is_zero() -> None:
    """Four unit steps return to even parity (§3.7, Lemma 2)."""
    assert Square4D(1, 1, 1, 1).parity() == 0


def test_parity_far_corner() -> None:
    """``π(7,7,7,7) = 28 mod 2 = 0``."""
    assert Square4D(7, 7, 7, 7).parity() == 0


@given(sq=squares_strategy)
def test_parity_returns_zero_or_one(sq: Square4D) -> None:
    """``π`` is a mod-2 invariant (§3.7, Lemma 2) so its range is ``{0, 1}``."""
    assert sq.parity() in (0, 1)


@given(sq=squares_strategy)
def test_parity_matches_coordinate_sum(sq: Square4D) -> None:
    """Definitional: ``π(x,y,z,w) = (x+y+z+w) mod 2`` (§3.7, Lemma 2)."""
    assert sq.parity() == (sq.x + sq.y + sq.z + sq.w) % 2


# --- chebyshev_distance ------------------------------------------------------


def test_chebyshev_distance_to_self_is_zero() -> None:
    assert Square4D(3, 4, 5, 6).chebyshev_distance(Square4D(3, 4, 5, 6)) == 0


def test_chebyshev_distance_is_max_coord_delta() -> None:
    """Paper §3.2, Definition 1: ``d∞ = max{|Δx|,|Δy|,|Δz|,|Δw|}``."""
    a = Square4D(0, 0, 0, 0)
    b = Square4D(1, 2, 3, 4)
    assert a.chebyshev_distance(b) == 4


def test_chebyshev_distance_negative_deltas_take_absolute_value() -> None:
    a = Square4D(7, 7, 7, 7)
    b = Square4D(0, 5, 7, 7)
    # Deltas: 7, 2, 0, 0 → max = 7.
    assert a.chebyshev_distance(b) == 7


def test_chebyshev_distance_adjacent_squares_equal_one() -> None:
    """Adjacency ⇔ ``d∞ = 1`` (paper §3.2, Definition 1)."""
    a = Square4D(3, 3, 3, 3)
    for delta in [(1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 0), (0, 0, 0, 1),
                  (1, 1, 0, 0), (1, 1, 1, 1), (-1, 1, -1, 1)]:
        b = Square4D(a.x + delta[0], a.y + delta[1], a.z + delta[2], a.w + delta[3])
        assert a.chebyshev_distance(b) == 1


@given(a=squares_strategy, b=squares_strategy)
def test_chebyshev_distance_is_symmetric(a: Square4D, b: Square4D) -> None:
    """``d∞`` is a metric, so symmetric."""
    assert a.chebyshev_distance(b) == b.chebyshev_distance(a)


@given(a=squares_strategy, b=squares_strategy)
def test_chebyshev_distance_is_nonnegative(a: Square4D, b: Square4D) -> None:
    assert a.chebyshev_distance(b) >= 0


@given(a=squares_strategy, b=squares_strategy)
def test_chebyshev_distance_zero_iff_equal(a: Square4D, b: Square4D) -> None:
    assert (a.chebyshev_distance(b) == 0) == (a == b)
