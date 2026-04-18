"""Domain-specific exceptions for chess4d.

Citations refer to Oana & Chiru, *A Mathematical Framework for
Four-Dimensional Chess*, MDPI AppliedMath 6(3):48, 2026
(DOI 10.3390/appliedmath6030048).
"""

from __future__ import annotations


class IllegalMoveError(ValueError):
    """Raised when :meth:`Board4D.push` rejects a move.

    Covers: no piece on the from-square, piece of a type not yet supported
    by Deliverable 2 (anything other than rook), target not reachable
    under the rook's displacement set (§3.5), intervening blocker, or
    target occupied by a friendly piece.

    King-safety (paper §3.4, Definition 3) is *not* enforced here; the
    legality pipeline lives in a later deliverable.
    """
