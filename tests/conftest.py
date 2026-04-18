"""Shared pytest fixtures and Hypothesis strategies for chess4d.

Citations refer to Oana & Chiru, *A Mathematical Framework for
Four-Dimensional Chess*, MDPI AppliedMath 6(3):48, 2026
(DOI 10.3390/appliedmath6030048).
"""

from __future__ import annotations

import itertools
from typing import Iterator

from hypothesis import strategies as st

from chess4d import BOARD_SIZE, Square4D


def all_squares() -> Iterator[Square4D]:
    """Enumerate every square in ``B = {0,…,7}^4`` (paper §3.1, 0-based)."""
    for x, y, z, w in itertools.product(range(BOARD_SIZE), repeat=4):
        yield Square4D(x, y, z, w)


coord_strategy = st.integers(min_value=0, max_value=BOARD_SIZE - 1)
"""Draw a single valid 0-based coordinate in ``[0, BOARD_SIZE)``."""

squares_strategy = st.builds(Square4D, coord_strategy, coord_strategy, coord_strategy, coord_strategy)
"""Draw a uniformly random in-bounds :class:`Square4D`."""

interior_coord_strategy = st.integers(min_value=1, max_value=BOARD_SIZE - 2)
interior_squares_strategy = st.builds(
    Square4D,
    interior_coord_strategy,
    interior_coord_strategy,
    interior_coord_strategy,
    interior_coord_strategy,
)
"""Draw a strictly-interior :class:`Square4D` (no coordinate on the boundary)."""
