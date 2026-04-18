"""Game state layer (paper §3.4, Definitions 3-5).

:class:`GameState` wraps a :class:`~chess4d.board.Board4D` with the
minimum additional state Phase 4 needs — currently just
``side_to_move``. Subsequent phases will add castling rights, an
en-passant target, the halfmove clock, and a repetition-hash history;
all of those live here (game-level), not on :class:`Board4D` which stays
at the placement-plus-pseudo-legal-push/pop layer.

The legality filter (§3.4 Def 3) lives in :meth:`GameState.push` and
:meth:`GameState.legal_moves`: a move is legal iff, after application,
no king of the moving side is attacked. Remark 1 is honored
automatically by checking *all* friendly kings via
:func:`chess4d.legality.any_king_attacked`, not just one.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from chess4d.board import Board4D
from chess4d.errors import IllegalMoveError
from chess4d.legality import _all_pseudo_legal_moves, any_king_attacked
from chess4d.types import Color, Move4D


@dataclass
class GameState:
    """A 4D-chess game state: piece placement plus ``side_to_move``.

    The legality filter lives in :meth:`push` and :meth:`legal_moves`;
    :class:`Board4D` remains pseudo-legal and does not know about
    side-to-move or king-safety.

    ``side_to_move`` is mutable (flipped by :meth:`push` / :meth:`pop`),
    so the dataclass is explicitly unhashable.
    """

    board: Board4D
    side_to_move: Color

    # @dataclass already sets __hash__ = None for mutable classes; spelling
    # it out makes the intent obvious alongside Board4D's own disabling.
    __hash__ = None  # type: ignore[assignment]

    def push(self, move: Move4D) -> None:
        """Apply ``move`` with full legality enforcement (§3.4 Def 3).

        Raises :class:`~chess4d.errors.IllegalMoveError` if the moving
        piece's color does not match ``side_to_move``, if the move is
        not pseudo-legal (propagated from :meth:`Board4D.push`), or if
        any friendly king would be attacked after the move.

        On any legality failure the underlying board is left
        bit-identical to its pre-call state, and ``side_to_move`` is
        unchanged.
        """
        piece = self.board.occupant(move.from_sq)
        if piece is None:
            # Defer to Board4D for the exact "no piece on X" message.
            self.board.push(move)
            return  # pragma: no cover — Board4D.push guarantees a raise.
        if piece.color != self.side_to_move:
            raise IllegalMoveError(
                f"It is {self.side_to_move.name}'s turn; "
                f"{move.from_sq} holds a {piece.color.name} piece."
            )
        self.board.push(move)
        if any_king_attacked(self.side_to_move, self.board):
            self.board.pop()
            raise IllegalMoveError(
                f"Move {move} leaves a {self.side_to_move.name} king in check "
                "(§3.4 Def 3, Remark 1)."
            )
        self.side_to_move = Color(1 - self.side_to_move)

    def pop(self) -> Move4D:
        """Undo the most recent :meth:`push`, restoring ``side_to_move``.

        Returns the move that was undone. Raises :class:`IndexError` if
        the board's undo stack is empty — the same failure mode as
        :meth:`Board4D.pop`.
        """
        move = self.board.pop()
        self.side_to_move = Color(1 - self.side_to_move)
        return move

    def legal_moves(self) -> Iterator[Move4D]:
        """Yield every legal move for ``side_to_move`` in the current state.

        Implementation uses make-unmake on the underlying board: each
        pseudo-legal candidate is pushed, king-safety is checked, and
        the candidate is popped whether or not it's legal. The board is
        thus bit-identical before and after iteration (assuming the
        caller does not mutate it mid-iteration).

        The candidate list is materialized before iteration so that
        pushes made during the loop do not disturb the generator that
        enumerates pseudo-legal moves.
        """
        candidates = list(_all_pseudo_legal_moves(self.side_to_move, self.board))
        for move in candidates:
            self.board.push(move)
            safe = not any_king_attacked(self.side_to_move, self.board)
            self.board.pop()
            if safe:
                yield move

    def in_check(self) -> bool:
        """Return ``True`` iff any ``side_to_move`` king is under attack.

        Paper §3.4 Def 4, generalized to multi-king (Remark 1): ``P`` is
        in check iff the enemy attack set intersects ``K_P(s)``.
        """
        return any_king_attacked(self.side_to_move, self.board)

    def is_checkmate(self) -> bool:
        """Return ``True`` iff ``side_to_move`` is in check and has no legal moves.

        Paper §3.4 Def 5.
        """
        return self.in_check() and not any(self.legal_moves())

    def is_stalemate(self) -> bool:
        """Return ``True`` iff ``side_to_move`` is not in check and has no legal moves.

        Paper §3.4 Def 5 (stalemate branch).
        """
        return not self.in_check() and not any(self.legal_moves())
