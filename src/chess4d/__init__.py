"""chess4d — Python reference implementation of Oana & Chiru (2026).

Paper
-----
Oana & Chiru, *A Mathematical Framework for Four-Dimensional Chess*,
MDPI AppliedMath 6(3):48, 2026. DOI 10.3390/appliedmath6030048.
The source document lives at ``hoodoos/oana-chiru-2026.xml`` and is the
authoritative spec for this package; section numbers referenced in
docstrings refer to that document.

Coordinate convention
---------------------
0-based internally (0..7 per axis), matching the reference UI described
in the paper. The paper's 1-based ``{1,…,8}^4`` notation is preserved in
docstrings for readability; conversion happens only at the UI boundary.
"""

from chess4d.board import Board4D
from chess4d.errors import IllegalMoveError
from chess4d.pieces import bishop_moves, knight_moves, queen_moves, rook_moves
from chess4d.types import (
    BOARD_SIZE,
    Color,
    Move4D,
    PawnAxis,
    Piece,
    PieceType,
    Square4D,
)

__all__ = [
    "BOARD_SIZE",
    "Board4D",
    "Color",
    "IllegalMoveError",
    "Move4D",
    "PawnAxis",
    "Piece",
    "PieceType",
    "Square4D",
    "bishop_moves",
    "knight_moves",
    "queen_moves",
    "rook_moves",
]
