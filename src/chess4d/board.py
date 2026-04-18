"""Minimal 4D board (paper §3.1, §3.3).

Piece-list representation: occupied coordinates are stored in a
``dict[Square4D, Piece]`` rather than a dense 4096-cell array, since the
initial position has only ~896 pieces (paper §3.3) and most cells are
empty throughout the game.

Deliverable 2 scope: construction, occupancy lookup, ``place`` /
``remove`` mutators, structural equality, and rook-only ``push`` /
``pop`` with an undo stack. Side-to-move, castling rights, en-passant
target, half-move clock, and the repetition hash arrive with the
legality pipeline in a later deliverable.
"""

from __future__ import annotations

from typing import Optional

from chess4d.errors import IllegalMoveError
from chess4d.geometry import ROOK_NEIGHBORS
from chess4d.types import Move4D, Piece, PieceType, Square4D


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

        Deliverable 2 only supports rook moves. Raises
        :class:`~chess4d.errors.IllegalMoveError` if:

        * ``move.from_sq`` is empty;
        * the moving piece is not a rook (D2 limitation);
        * ``move.to_sq`` is not empty-board reachable by a rook from
          ``move.from_sq`` (i.e. not a single-coordinate neighbor, §3.5);
        * any intervening square along the ray is occupied;
        * ``move.to_sq`` holds a friendly piece.

        King-safety (§3.4, Definition 3) is *not* enforced here.
        """
        piece = self._squares.get(move.from_sq)
        if piece is None:
            raise IllegalMoveError(f"No piece on {move.from_sq}.")
        if piece.piece_type is not PieceType.ROOK:
            raise IllegalMoveError(
                f"Only rook moves are supported in Deliverable 2; got {piece.piece_type.name}."
            )
        if move.to_sq not in ROOK_NEIGHBORS[move.from_sq]:
            raise IllegalMoveError(
                f"{move.to_sq} is not rook-reachable from {move.from_sq} (paper §3.5)."
            )
        self._walk_ray_or_raise(move.from_sq, move.to_sq)

        captured = self._squares.get(move.to_sq)
        if captured is not None and captured.color == piece.color:
            raise IllegalMoveError(
                f"{move.to_sq} is occupied by a friendly {captured.piece_type.name}."
            )

        # Apply: move the piece, capturing if the target has an opponent.
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

    def _walk_ray_or_raise(self, from_sq: Square4D, to_sq: Square4D) -> None:
        """Confirm the straight ray from ``from_sq`` to ``to_sq`` (exclusive of
        both endpoints) is empty. Caller must have already verified the two
        squares are rook-reachable (single-axis difference)."""
        # Exactly one axis differs (guaranteed by the ROOK_NEIGHBORS check).
        delta = (to_sq.x - from_sq.x, to_sq.y - from_sq.y,
                 to_sq.z - from_sq.z, to_sq.w - from_sq.w)
        axis = next(i for i, d in enumerate(delta) if d != 0)
        step = 1 if delta[axis] > 0 else -1
        distance = abs(delta[axis])
        for k in range(1, distance):
            coords = list(from_sq)
            coords[axis] += k * step
            intermediate = Square4D(*coords)
            if intermediate in self._squares:
                raise IllegalMoveError(
                    f"Ray from {from_sq} to {to_sq} is blocked at {intermediate}."
                )

    # --- equality ------------------------------------------------------------

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Board4D):
            return NotImplemented
        return self._squares == other._squares

    # Board4D is mutable, so disabling hashing is intentional.
    __hash__ = None  # type: ignore[assignment]
