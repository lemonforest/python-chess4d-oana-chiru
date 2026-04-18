"""Per-piece move generators (paper §3.5, §3.7–§3.10).

Phase 1 shipped rook; Phase 2 added bishop; Phase 3 adds queen, knight,
king, and pawn. Sliding pieces (rook, bishop, queen) share a single
loop in :mod:`chess4d.pieces._common`. Knight and king are leapers and
are generated directly from their NEIGHBORS tables. Pawn is the only
piece with color- and axis-dependent geometry and is dispatched
separately in :class:`~chess4d.board.Board4D`.
"""

from chess4d.pieces.bishop import bishop_moves
from chess4d.pieces.knight import knight_moves
from chess4d.pieces.queen import queen_moves
from chess4d.pieces.rook import rook_moves

__all__ = ["bishop_moves", "knight_moves", "queen_moves", "rook_moves"]
