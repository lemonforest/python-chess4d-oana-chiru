"""Pawn geometry-table invariants (paper §3.10, Definitions 11-14).

Citations refer to Oana & Chiru, *A Mathematical Framework for
Four-Dimensional Chess*, MDPI AppliedMath 6(3):48, 2026
(DOI 10.3390/appliedmath6030048).

Pawn geometry is keyed by ``(color, axis)`` — four tables:
``{WHITE, BLACK} × {Y, W}``. These tests verify that the tables match
the paper's definitions structurally, prior to any move-execution
semantics (which live in ``test_pawn_moves.py``).
"""

from __future__ import annotations

import pytest

from chess4d import BOARD_SIZE, Color, PawnAxis, Square4D
from chess4d.geometry import (
    PAWN_CAPTURES,
    PAWN_DIRECTION,
    PAWN_FORWARD_MOVES,
    PAWN_PROMOTION_RANK,
    PAWN_START_RANK,
)

from .conftest import all_squares


_KEYS: tuple[tuple[Color, PawnAxis], ...] = (
    (Color.WHITE, PawnAxis.Y),
    (Color.BLACK, PawnAxis.Y),
    (Color.WHITE, PawnAxis.W),
    (Color.BLACK, PawnAxis.W),
)


# --- direction / rank tables ------------------------------------------------


def test_direction_signs_are_symmetric() -> None:
    assert PAWN_DIRECTION[(Color.WHITE, PawnAxis.Y)] == +1
    assert PAWN_DIRECTION[(Color.BLACK, PawnAxis.Y)] == -1
    assert PAWN_DIRECTION[(Color.WHITE, PawnAxis.W)] == +1
    assert PAWN_DIRECTION[(Color.BLACK, PawnAxis.W)] == -1


def test_start_and_promotion_ranks_are_consistent() -> None:
    for color, axis in _KEYS:
        start = PAWN_START_RANK[(color, axis)]
        promo = PAWN_PROMOTION_RANK[(color, axis)]
        direction = PAWN_DIRECTION[(color, axis)]
        # The forward axis has 8 coords; start is second-from-home, promo is the far boundary.
        if color is Color.WHITE:
            assert start == 1
            assert promo == BOARD_SIZE - 1
        else:
            assert start == BOARD_SIZE - 2
            assert promo == 0
        # A pawn advancing from start takes direction × (promo - start) steps to promote:
        # white: +1 × 6 = 6, black: -1 × -6 = 6.
        assert direction * (promo - start) == BOARD_SIZE - 2


# --- forward-move table -----------------------------------------------------


@pytest.mark.parametrize("key", _KEYS)
def test_forward_table_covers_every_square(key: tuple[Color, PawnAxis]) -> None:
    table = PAWN_FORWARD_MOVES[key]
    assert set(table.keys()) == set(all_squares())


@pytest.mark.parametrize("key", _KEYS)
def test_forward_one_step_when_past_start_rank(key: tuple[Color, PawnAxis]) -> None:
    color, axis = key
    direction = PAWN_DIRECTION[key]
    start = PAWN_START_RANK[key]
    promo = PAWN_PROMOTION_RANK[key]
    axis_index = int(axis)
    for origin in all_squares():
        forward = origin[axis_index]
        # Past-the-start-rank, in-bounds, not yet on promo: single step.
        if forward != start and forward != promo:
            targets = PAWN_FORWARD_MOVES[key][origin]
            assert len(targets) == 1
            target = targets[0]
            # target differs only in the forward axis, by one step in direction.
            for i in range(4):
                delta = target[i] - origin[i]
                assert delta == (direction if i == axis_index else 0)


@pytest.mark.parametrize("key", _KEYS)
def test_forward_two_step_from_start_rank(key: tuple[Color, PawnAxis]) -> None:
    color, axis = key
    direction = PAWN_DIRECTION[key]
    start = PAWN_START_RANK[key]
    axis_index = int(axis)
    for origin in all_squares():
        if origin[axis_index] != start:
            continue
        targets = PAWN_FORWARD_MOVES[key][origin]
        assert len(targets) == 2
        one, two = targets
        assert one[axis_index] == start + direction
        assert two[axis_index] == start + 2 * direction
        # Other coordinates unchanged.
        for i in range(4):
            if i == axis_index:
                continue
            assert one[i] == origin[i]
            assert two[i] == origin[i]


@pytest.mark.parametrize("key", _KEYS)
def test_forward_empty_on_promotion_rank(key: tuple[Color, PawnAxis]) -> None:
    """A pawn sitting on the promo rank has no legal forward target —
    the one-step would leave the board."""
    promo = PAWN_PROMOTION_RANK[key]
    axis_index = int(PawnAxis(key[1]))
    for origin in all_squares():
        if origin[axis_index] == promo:
            assert PAWN_FORWARD_MOVES[key][origin] == ()


# --- capture table ----------------------------------------------------------


@pytest.mark.parametrize("key", _KEYS)
def test_captures_lie_in_x_forward_plane(key: tuple[Color, PawnAxis]) -> None:
    """§3.10 Def 13: captures stay in the 2D plane of the x-axis and the
    forward axis. All other coordinates must equal the origin's."""
    _, axis = key
    axis_index = int(axis)
    other_axes = [i for i in range(4) if i not in (0, axis_index)]
    for origin in all_squares():
        for target in PAWN_CAPTURES[key][origin]:
            for i in other_axes:
                assert target[i] == origin[i]


@pytest.mark.parametrize("key", _KEYS)
def test_captures_are_diagonal_offsets(key: tuple[Color, PawnAxis]) -> None:
    direction = PAWN_DIRECTION[key]
    axis_index = int(key[1])
    for origin in all_squares():
        for target in PAWN_CAPTURES[key][origin]:
            dx = target.x - origin.x
            df = target[axis_index] - origin[axis_index]
            assert abs(dx) == 1
            assert df == direction


@pytest.mark.parametrize("key", _KEYS)
def test_capture_count_respects_boundaries(key: tuple[Color, PawnAxis]) -> None:
    direction = PAWN_DIRECTION[key]
    axis_index = int(key[1])
    for origin in all_squares():
        expected = 0
        if 0 <= origin[axis_index] + direction < BOARD_SIZE:
            if origin.x - 1 >= 0:
                expected += 1
            if origin.x + 1 < BOARD_SIZE:
                expected += 1
        assert len(PAWN_CAPTURES[key][origin]) == expected


def test_y_pawn_never_captures_outside_xy_plane() -> None:
    """Regression for §3.10 Def 13 — no XZ / YZ / ZW captures."""
    for color in (Color.WHITE, Color.BLACK):
        for origin in all_squares():
            for target in PAWN_CAPTURES[(color, PawnAxis.Y)][origin]:
                assert target.z == origin.z
                assert target.w == origin.w


def test_w_pawn_never_captures_outside_xw_plane() -> None:
    for color in (Color.WHITE, Color.BLACK):
        for origin in all_squares():
            for target in PAWN_CAPTURES[(color, PawnAxis.W)][origin]:
                assert target.y == origin.y
                assert target.z == origin.z


# --- cross-table consistency ------------------------------------------------


def test_y_and_w_tables_are_axis_swaps() -> None:
    """Under the (y ↔ w) coordinate swap, a Y-pawn's geometry maps to a
    W-pawn's geometry of the same color. This is the Y↔W symmetry the
    paper calls out in §3.10 (one rule parameterized by axis)."""

    def swap_yw(sq: Square4D) -> Square4D:
        return Square4D(sq.x, sq.w, sq.z, sq.y)

    for color in (Color.WHITE, Color.BLACK):
        for origin in all_squares():
            swapped_origin = swap_yw(origin)
            assert tuple(swap_yw(t) for t in PAWN_FORWARD_MOVES[(color, PawnAxis.Y)][origin]) == (
                PAWN_FORWARD_MOVES[(color, PawnAxis.W)][swapped_origin]
            )
            assert tuple(swap_yw(t) for t in PAWN_CAPTURES[(color, PawnAxis.Y)][origin]) == (
                PAWN_CAPTURES[(color, PawnAxis.W)][swapped_origin]
            )
