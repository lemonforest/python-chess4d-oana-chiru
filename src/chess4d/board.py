"""Minimal 4D board (paper §3.1, §3.3).

Piece-list representation: occupied coordinates are stored in a
``dict[Square4D, Piece]`` rather than a dense 4096-cell array, since the
initial position has only ~896 pieces (paper §3.3) and most cells are
empty throughout the game.

``push`` / ``pop`` accept moves for every piece type registered in
:data:`_PIECE_GEOMETRY`. Phase 1 registered the rook; Phase 2 adds the
bishop. Other piece types raise :class:`~chess4d.errors.IllegalMoveError`
until their own phase lands. Side-to-move, castling rights, en-passant
target, half-move clock, and the repetition hash arrive with the
legality pipeline in a later deliverable.
"""

from __future__ import annotations

from typing import Mapping, Optional

from chess4d.errors import IllegalMoveError
from chess4d.geometry import (
    BISHOP_NEIGHBORS,
    BISHOP_RAYS,
    ROOK_NEIGHBORS,
    ROOK_RAYS,
)
from chess4d.types import Move4D, Piece, PieceType, Square4D

_RaysMap = Mapping[Square4D, tuple[tuple[Square4D, ...], ...]]
_NeighborsMap = Mapping[Square4D, frozenset[Square4D]]


_PIECE_GEOMETRY: dict[PieceType, tuple[_RaysMap, _NeighborsMap]] = {
    PieceType.ROOK: (ROOK_RAYS, ROOK_NEIGHBORS),
    PieceType.BISHOP: (BISHOP_RAYS, BISHOP_NEIGHBORS),
}
"""Dispatch table from :class:`PieceType` to ``(RAYS, NEIGHBORS)`` mappings.

Adding a new piece type is purely additive: register an entry here
(leapers use singleton rays) and :meth:`Board4D.push` picks it up
without any branching change.
"""


class Board4D:
    """A 4D chess board storing occupied squares as a piece list.

    Structural equality (``__eq__``) compares the piece placement only;
    the undo stack is a transient implementation detail and is ignored.
    """

    __slots__ = ("_squares", "_undo")

    def __init__(self) -> None:
        self._squares: dict[Square4D, Piece] = {}
        # Undo record shape: (move, captured_piece_or_None).
        self._undo: list[tuple[Move4D, Optional[Piece]]] = []

    # --- state lookup --------------------------------------------------------

    def occupant(self, sq: Square4D) -> Optional[Piece]:
        """Return the :class:`Piece` at ``sq``, or ``None`` if the square is empty."""
        return self._squares.get(sq)

    # --- raw placement (for setup / test scaffolding) ------------------------

    def place(self, sq: Square4D, piece: Piece) -> None:
        """Put ``piece`` on ``sq``.

        Raises :class:`ValueError` if ``sq`` is already occupied. This is a
        programming-error signal, not a move-legality signal — it prevents
        silent state corruption when the caller has lost track of the
        board.
        """
        if sq in self._squares:
            raise ValueError(f"Square {sq} is already occupied by {self._squares[sq]!r}.")
        self._squares[sq] = piece

    def remove(self, sq: Square4D) -> Piece:
        """Remove and return the piece at ``sq``. Raises :class:`KeyError` if empty."""
        return self._squares.pop(sq)

    # --- move application ----------------------------------------------------

    def push(self, move: Move4D) -> None:
        """Apply ``move`` to the board (paper §3.4, ``s' = apply(m, s)``).

        Raises :class:`~chess4d.errors.IllegalMoveError` if:

        * ``move.from_sq`` is empty;
        * the moving piece's type is not yet registered in
          :data:`_PIECE_GEOMETRY`;
        * ``move.to_sq`` is not empty-board reachable for that piece type;
        * any intervening square along the ray is occupied;
        * ``move.to_sq`` holds a friendly piece.

        King-safety (§3.4, Definition 3) is *not* enforced here.
        """
        piece = self._squares.get(move.from_sq)
        if piece is None:
            raise IllegalMoveError(f"No piece on {move.from_sq}.")
        geometry = _PIECE_GEOMETRY.get(piece.piece_type)
        if geometry is None:
            raise IllegalMoveError(
                f"{piece.piece_type.name} moves are not yet supported in this phase."
            )
        rays, neighbors = geometry
        if move.to_sq not in neighbors[move.from_sq]:
            raise IllegalMoveError(
                f"{move.to_sq} is not reachable by {piece.piece_type.name} "
                f"from {move.from_sq}."
            )
        self._walk_ray_or_raise(rays, move.from_sq, move.to_sq)

        captured = self._squares.get(move.to_sq)
        if captured is not None and captured.color == piece.color:
            raise IllegalMoveError(
                f"{move.to_sq} is occupied by a friendly {captured.piece_type.name}."
            )

        if captured is not None:
            del self._squares[move.to_sq]
        del self._squares[move.from_sq]
        self._squares[move.to_sq] = piece
        self._undo.append((move, captured))

    def pop(self) -> Move4D:
        """Undo the most recent :meth:`push`.

        Returns the move that was undone. Raises :class:`IndexError` if
        the undo stack is empty.
        """
        move, captured = self._undo.pop()
        piece = self._squares.pop(move.to_sq)
        self._squares[move.from_sq] = piece
        if captured is not None:
            self._squares[move.to_sq] = captured
        return move

    # --- helpers -------------------------------------------------------------

    def _walk_ray_or_raise(
        self, rays: _RaysMap, from_sq: Square4D, to_sq: Square4D
    ) -> None:
        """Find the ray in ``rays[from_sq]`` containing ``to_sq`` and verify
        that every square strictly between them is empty.

        Caller has already checked reachability via the ``_NEIGHBORS``
        mapping, so ``to_sq`` is guaranteed to be on some ray; the
        final ``raise`` is defensive and indicates an internal
        inconsistency between the rays and neighbors tables.
        """
        for ray in rays[from_sq]:
            if to_sq in ray:
                # Ray is ordered nearest-to-farthest; squares strictly
                # between the origin and `to_sq` are the prefix up to
                # (but excluding) `to_sq`'s index.
                idx = ray.index(to_sq)
                for intermediate in ray[:idx]:
                    if intermediate in self._squares:
                        raise IllegalMoveError(
                            f"Ray from {from_sq} to {to_sq} is blocked at {intermediate}."
                        )
                return
        raise IllegalMoveError(  # pragma: no cover — defensive, unreachable in practice
            f"No ray from {from_sq} contains {to_sq} (internal geometry error)."
        )

    # --- equality ------------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Board4D):
            return NotImplemented
        return self._squares == other._squares

    # Board4D is mutable, so disabling hashing is intentional.
    __hash__ = None  # type: ignore[assignment]
