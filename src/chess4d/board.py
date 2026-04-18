"""Minimal 4D board (paper §3.1, §3.3).

Piece-list representation: occupied coordinates are stored in a
``dict[Square4D, Piece]`` rather than a dense 4096-cell array, since the
initial position has only ~896 pieces (paper §3.3) and most cells are
empty throughout the game.

This module is a stub during Deliverable 1. The implementation lands in
Deliverable 2 once the rook-adjacency tests drive out the minimal surface
area (``occupant`` lookup + ``place``/``remove`` mutators).
"""

from __future__ import annotations

from typing import Optional

from chess4d.types import Piece, Square4D


class Board4D:
    """A 4D chess board storing occupied squares as a piece list.

    The full state ``s`` in paper §3.4 also includes side-to-move, castling
    rights, en-passant target, half-move clock, and repetition hash. Those
    fields will be added alongside the legality pipeline in a later
    deliverable; this class currently models only the piece placement.
    """

    def __init__(self) -> None:
        raise NotImplementedError("Board4D will be implemented in Deliverable 2 (TDD).")

    def occupant(self, sq: Square4D) -> Optional[Piece]:
        """Return the :class:`Piece` at ``sq``, or ``None`` if the square is empty."""
        raise NotImplementedError("Board4D.occupant will be implemented in Deliverable 2.")
