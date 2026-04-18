"""Core types for chess4d.

All citations refer to Oana & Chiru, *A Mathematical Framework for
Four-Dimensional Chess*, MDPI AppliedMath 6(3):48, 2026
(DOI 10.3390/appliedmath6030048).
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import NamedTuple, Optional

BOARD_SIZE: int = 8
"""Extent of each axis in the board domain.

Paper §3.1 defines ``B = {1,…,8}^4 ⊂ Z^4`` (4096 cells). This package uses
0-based indexing internally, so ``B = {0,…,7}^4``. Conversion to the paper's
1-based notation is a UI-boundary concern.
"""


class Color(IntEnum):
    """Player colors (paper §3.3–§3.4).

    Values are chosen so the opponent of player ``P`` is ``Color(1 - P)``,
    matching the paper's ``1 − P`` convention used in Definitions 2–4.
    """

    WHITE = 0
    BLACK = 1


class PieceType(IntEnum):
    """Piece kinds (paper §3.5, §3.7–§3.10).

    The queen (§3.8, Definition 7) is deliberately restricted to 1- and
    2-axis moves. Adding 3- or 4-axis diagonals would collapse
    bishop/rook/queen into a single class — do not extend this enum with
    such moves without revisiting the paper.
    """

    PAWN = 1    # §3.10, Definitions 11, 12
    KNIGHT = 2  # §3.8, Definition 8
    BISHOP = 3  # §3.7, Definition 6
    ROOK = 4    # §3.5, Theorem 1
    QUEEN = 5   # §3.8, Definition 7  (1- and 2-axis only)
    KING = 6    # §3.9, Definition 9


class PawnAxis(IntEnum):
    """Forward axis of a pawn, fixed at initialization (paper §3.10, Def. 11).

    A pawn's orientation is set when the piece is placed and never changes.
    Pawn rule logic is implemented once and parameterized by axis, so the
    same code path handles Y-oriented and W-oriented pawns with the axis
    index swapped.

    Values match the coordinate index used by ``Square4D`` (0=x, 1=y, 2=z,
    3=w), so ``sq[axis]`` selects the forward coordinate directly.
    """

    Y = 1  # Y-oriented pawn: forward is ±e_y; captures on XY diagonals.
    W = 3  # W-oriented pawn: forward is ±e_w; captures on XW diagonals.


class Square4D(NamedTuple):
    """A square in ``B = {0,…,7}^4 ⊂ Z^4`` (paper §3.1).

    Coordinates are stored in ``(x, y, z, w)`` order, matching the paper's
    tuple convention. 0-based internally; the paper's 1-based form is used
    only in docstrings and at UI boundaries.

    ``Square4D`` is a :class:`~typing.NamedTuple` so that tuple unpacking,
    structural equality, and hashing are free — important for the hot
    move-generation loop (§3.5 and friends).
    """

    x: int
    y: int
    z: int
    w: int

    def in_bounds(self) -> bool:
        """Return True iff every coordinate is in ``[0, BOARD_SIZE)``.

        Corresponds to membership in the board ``B`` (paper §3.1).
        """
        raise NotImplementedError("Square4D.in_bounds will be implemented in Deliverable 2 (TDD).")

    def parity(self) -> int:
        """Return ``π(x, y, z, w) = (x + y + z + w) mod 2`` (paper §3.7, Lemma 2).

        Invariant under every bishop move; partitions the bishop graph into
        exactly two connected components (§3.7, Theorem 4). Rook moves flip
        parity by ``d mod 2`` where ``d`` is the step length (§3.8,
        Proposition 2(i)); knight moves always flip parity (Proposition
        2(iii)).
        """
        raise NotImplementedError("Square4D.parity will be implemented in Deliverable 2 (TDD).")

    def chebyshev_distance(self, other: "Square4D") -> int:
        """Return ``d∞(self, other) = max{|Δx|, |Δy|, |Δz|, |Δw|}``.

        The Chebyshev metric on ``Z^4`` (paper §3.2, Definition 1). Two
        squares are adjacent iff this distance equals 1; any interior
        square therefore has exactly ``3^4 − 1 = 80`` neighbors (Lemma 1).
        """
        raise NotImplementedError(
            "Square4D.chebyshev_distance will be implemented in Deliverable 2 (TDD)."
        )


@dataclass(frozen=True, slots=True)
class Piece:
    """A colored piece (paper §3.3).

    ``pawn_axis`` must be non-None iff ``piece_type == PieceType.PAWN``,
    and is fixed for the lifetime of the piece (§3.10, Definition 11).
    The orientation is assigned at initial placement and does not change
    under any rule (including promotion — promotion changes ``piece_type``
    and clears ``pawn_axis``).

    Construction raises :class:`ValueError` if the axis invariant is
    violated (e.g. a non-pawn with a ``pawn_axis``, or a pawn without one).
    """

    color: Color
    piece_type: PieceType
    pawn_axis: Optional[PawnAxis] = None

    def __post_init__(self) -> None:
        if self.piece_type == PieceType.PAWN and self.pawn_axis is None:
            raise ValueError(
                "Piece(piece_type=PAWN) requires pawn_axis to be set (paper §3.10, Def. 11)."
            )
        if self.piece_type != PieceType.PAWN and self.pawn_axis is not None:
            raise ValueError(
                f"Piece(piece_type={self.piece_type.name}) must have pawn_axis=None; "
                "only pawns carry an axis (paper §3.10, Def. 11)."
            )


@dataclass(frozen=True, slots=True)
class Move4D:
    """A move on the 4D board (paper §3.5, §3.8–§3.10).

    The minimal form is ``(from_sq, to_sq)``. The identity of any captured
    piece is derived from the board state at apply-time rather than carried
    on the move (matching the convention in ``python-chess``).

    **Legality (paper §3.4, Definition 3).** A pseudo-legal move ``m`` is
    legal iff, after ``s' = apply(m, s)``, no king of the moving side is
    attacked in ``s'``. This generalizes single-king legality by
    quantifying over the full set of the side's kings; per Remark 1,
    saving only one king when multiple are attacked is insufficient.

    Flags
    -----
    promotion
        Non-None iff a pawn reaches its terminal rank on its forward axis
        (§3.10, Definition 12). The resulting piece keeps the mover's
        color and takes the specified type.
    is_castling
        The move is an X-axis castling move within a single ``(z, w)``
        -slice. The king's transit path must be safe against attacks from
        *any* ``(z', w')``-slice, even though the move itself is local
        (§3.9, Definition 10).
    is_en_passant
        The move is an en-passant capture. En passant is defined
        independently for Y-oriented and W-oriented pawns; mixed Y-vs-W
        en passant does not exist (§3.10, Definition 15).
    """

    from_sq: Square4D
    to_sq: Square4D
    promotion: Optional[PieceType] = None
    is_castling: bool = False
    is_en_passant: bool = False
