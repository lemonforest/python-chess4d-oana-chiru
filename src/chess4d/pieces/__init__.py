"""Per-piece move generators (paper §3.5, §3.7–§3.10).

Phase 1 shipped :mod:`chess4d.pieces.rook`; Phase 2 adds
:mod:`chess4d.pieces.bishop`. The remaining modules are stubs citing
their paper definitions; their generators land in later phases.
"""

from chess4d.pieces.bishop import bishop_moves
from chess4d.pieces.rook import rook_moves

__all__ = ["bishop_moves", "rook_moves"]
