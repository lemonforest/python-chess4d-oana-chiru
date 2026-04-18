"""Game state layer (paper §3.4, Definitions 3-5; §3.9 Def 10).

:class:`GameState` wraps a :class:`~chess4d.board.Board4D` with the
game-level state the legality pipeline and rule set require beyond
placement alone:

* ``side_to_move`` — whose turn it is (Phase 4).
* ``castling_rights`` — per-``(color, z, w, side)`` castling eligibility
  (Phase 5A, §3.9 Def 10).

Subsequent Phase 5 sub-phases add the en-passant target, halfmove
clock, and position-history hash. All of those live here (game-level),
not on :class:`Board4D` which stays at the placement-plus-pseudo-legal
push/pop layer.

The legality filter (§3.4 Def 3) lives in :meth:`GameState.push` and
:meth:`GameState.legal_moves`: a move is legal iff, after application,
no king of the moving side is attacked. Remark 1 is honored
automatically by checking *all* friendly kings via
:func:`chess4d.legality.any_king_attacked`, not just one.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterator, Optional

from chess4d.board import Board4D
from chess4d.errors import IllegalMoveError
from chess4d.legality import _all_pseudo_legal_moves, any_king_attacked, is_attacked
from chess4d.types import (
    BOARD_SIZE,
    CastleSide,
    CastlingRight,
    Color,
    Move4D,
    Piece,
    PieceType,
    Square4D,
)


@dataclass(frozen=True, slots=True)
class _GameStateUndo:
    """Per-push snapshot of GameState-level fields (Phase 5).

    Stored on :attr:`GameState._undo` and paired 1:1 with entries on
    :attr:`Board4D._undo` for non-castling moves; for castling,
    ``is_castling_compound`` is True and two board-level entries pair
    with this one game-level entry.
    """

    prior_castling_rights: frozenset[CastlingRight]
    is_castling_compound: bool


def _rook_home_right(color: Color, sq: Square4D) -> Optional[CastlingRight]:
    """Return the castling right associated with a rook on ``sq``, if any.

    A rook is at its "home square" when it sits on its color's back
    rank (``y = 0`` for white, ``y = BOARD_SIZE - 1`` for black) at
    ``x = 0`` (queenside) or ``x = BOARD_SIZE - 1`` (kingside).
    Otherwise returns ``None`` — the square is not a home square for
    this color and cannot affect castling rights.
    """
    back_y = 0 if color is Color.WHITE else BOARD_SIZE - 1
    if sq.y != back_y:
        return None
    if sq.x == 0:
        return (color, sq.z, sq.w, CastleSide.QUEENSIDE)
    if sq.x == BOARD_SIZE - 1:
        return (color, sq.z, sq.w, CastleSide.KINGSIDE)
    return None


def _revoke_rights_for_move(
    old_rights: frozenset[CastlingRight],
    move: Move4D,
    mover: Piece,
    captured: Optional[Piece],
) -> frozenset[CastlingRight]:
    """Return the castling-rights set after ``move``, per §3.9 Def 10.

    Rights are revoked when:

    * the mover is a king — both rights for the king's starting slice
      and color are removed;
    * the mover is a rook leaving its home square — that right is
      removed;
    * a rook is captured on its home square — the captured color's
      right for that corner is removed.

    Non-castling moves only; castling's own rights revocation is
    handled in :meth:`GameState._push_castling` (it removes both
    rights for the castling slice simultaneously).
    """
    to_revoke: set[CastlingRight] = set()
    if mover.piece_type is PieceType.KING:
        for side in CastleSide:
            to_revoke.add((mover.color, move.from_sq.z, move.from_sq.w, side))
    elif mover.piece_type is PieceType.ROOK:
        right = _rook_home_right(mover.color, move.from_sq)
        if right is not None:
            to_revoke.add(right)
    if captured is not None and captured.piece_type is PieceType.ROOK:
        right = _rook_home_right(captured.color, move.to_sq)
        if right is not None:
            to_revoke.add(right)
    if not to_revoke:
        return old_rights
    return old_rights - to_revoke


@dataclass
class GameState:
    """A 4D-chess game state: piece placement plus game-level fields.

    The legality filter lives in :meth:`push` and :meth:`legal_moves`;
    :class:`Board4D` remains pseudo-legal and does not know about
    side-to-move, castling rights, or king-safety.

    ``castling_rights`` defaults to the empty set so that hand-built
    test positions that don't care about castling work without
    plumbing. :func:`chess4d.startpos.initial_position` populates the
    full 112-right starting set.

    Mutable fields (``side_to_move``, ``castling_rights``, ``_undo``)
    are flipped/restored by :meth:`push`/:meth:`pop`, so the dataclass
    is explicitly unhashable.
    """

    board: Board4D
    side_to_move: Color
    castling_rights: frozenset[CastlingRight] = frozenset()
    _undo: list[_GameStateUndo] = field(default_factory=list, repr=False)

    __hash__ = None  # type: ignore[assignment]

    def push(self, move: Move4D) -> None:
        """Apply ``move`` with full legality enforcement (§3.4 Def 3).

        Raises :class:`~chess4d.errors.IllegalMoveError` if the moving
        piece's color does not match ``side_to_move``, if the move is
        not pseudo-legal (propagated from :meth:`Board4D.push`), or if
        any friendly king would be attacked after the move. Castling
        moves (``move.is_castling``) route through
        :meth:`_push_castling`, which enforces the extra §3.9 Def 10
        preconditions.

        On any legality failure the underlying board is left
        bit-identical to its pre-call state, and ``side_to_move`` /
        ``castling_rights`` are unchanged.
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
        if move.is_castling:
            self._push_castling(move, piece)
            return
        captured = self.board.occupant(move.to_sq)
        self.board.push(move)
        if any_king_attacked(self.side_to_move, self.board):
            self.board.pop()
            raise IllegalMoveError(
                f"Move {move} leaves a {self.side_to_move.name} king in check "
                "(§3.4 Def 3, Remark 1)."
            )
        self._undo.append(
            _GameStateUndo(
                prior_castling_rights=self.castling_rights,
                is_castling_compound=False,
            )
        )
        self.castling_rights = _revoke_rights_for_move(
            self.castling_rights, move, piece, captured
        )
        self.side_to_move = Color(1 - self.side_to_move)

    def _push_castling(self, move: Move4D, king: Piece) -> None:
        """Validate and apply a castling move (§3.9 Def 10).

        The move's ``from_sq`` is the king's starting square; its
        ``to_sq`` is the king's destination (±2 on the x-axis).
        Validates all six paper preconditions:

        1. Mover is a king (enforced by caller + this method).
        2. Castling right for ``(color, z, w, side)`` is present.
        3. Every square strictly between king and rook is empty.
        4. The side is not in check before the move.
        5. No square on the king's transit path (start, middle, end)
           is attacked by any enemy piece from any ``(z', w')`` slice
           (§3.9 Def 10 clause 3 — the "global attack" requirement).
        6. After the compound mutation (king + rook), no friendly king
           is attacked — standard post-move king-safety.

        On any failure the board and game-level state are left
        unchanged.
        """
        if king.piece_type is not PieceType.KING:
            raise IllegalMoveError(
                f"Castling move from {move.from_sq} requires a king, "
                f"found {king.piece_type.name}."
            )
        back_y = 0 if king.color is Color.WHITE else BOARD_SIZE - 1
        if move.from_sq.y != back_y or move.from_sq.x != 4:
            raise IllegalMoveError(
                f"Castling king must start at x=4, y={back_y}; "
                f"got {move.from_sq}."
            )
        dx = move.to_sq.x - move.from_sq.x
        if (
            dx not in (-2, 2)
            or move.to_sq.y != move.from_sq.y
            or move.to_sq.z != move.from_sq.z
            or move.to_sq.w != move.from_sq.w
        ):
            raise IllegalMoveError(
                f"Castling destination must be ±2 on x within the same slice; "
                f"got {move.from_sq} → {move.to_sq}."
            )
        z, w = move.from_sq.z, move.from_sq.w
        if dx == 2:
            side = CastleSide.KINGSIDE
            rook_from_x = BOARD_SIZE - 1
            rook_to_x = move.to_sq.x - 1  # = 5
            between_xs: tuple[int, ...] = (5, 6)
            transit_xs: tuple[int, ...] = (4, 5, 6)
        else:
            side = CastleSide.QUEENSIDE
            rook_from_x = 0
            rook_to_x = move.to_sq.x + 1  # = 3
            between_xs = (1, 2, 3)
            transit_xs = (4, 3, 2)
        right: CastlingRight = (king.color, z, w, side)
        if right not in self.castling_rights:
            raise IllegalMoveError(
                f"No castling right for {right} (§3.9 Def 10 clause 1)."
            )
        for bx in between_xs:
            between_sq = Square4D(bx, back_y, z, w)
            if self.board.occupant(between_sq) is not None:
                raise IllegalMoveError(
                    f"Castling path blocked at {between_sq} "
                    "(§3.9 Def 10 clause 2)."
                )
        rook_from = Square4D(rook_from_x, back_y, z, w)
        rook_piece = self.board.occupant(rook_from)
        if (
            rook_piece is None
            or rook_piece.piece_type is not PieceType.ROOK
            or rook_piece.color != king.color
        ):
            raise IllegalMoveError(
                f"Castling requires a friendly rook at {rook_from}."
            )
        if any_king_attacked(king.color, self.board):
            raise IllegalMoveError(
                "Cannot castle while in check (§3.9 Def 10 clause 3)."
            )
        enemy = Color(1 - king.color)
        for tx in transit_xs:
            if is_attacked(Square4D(tx, back_y, z, w), enemy, self.board):
                raise IllegalMoveError(
                    f"Castling king's transit square (x={tx}) is attacked "
                    "(§3.9 Def 10 clause 3)."
                )
        # All preconditions satisfied — apply the compound mutation.
        # Use _push_unchecked because the king's 2-square jump and the
        # rook's x-axis slide to the opposite side of the king aren't
        # pseudo-legal single-piece moves; GameState has already
        # validated everything above.
        rook_to = Square4D(rook_to_x, back_y, z, w)
        self.board._push_unchecked(move)
        self.board._push_unchecked(Move4D(rook_from, rook_to))
        if any_king_attacked(king.color, self.board):
            # Should not be reachable given the transit-safety check, but
            # multi-king discovered checks on *other* kings can trip this.
            self.board.pop()
            self.board.pop()
            raise IllegalMoveError(
                f"Castling leaves a {king.color.name} king in check "
                "(§3.4 Def 3, Remark 1)."
            )
        self._undo.append(
            _GameStateUndo(
                prior_castling_rights=self.castling_rights,
                is_castling_compound=True,
            )
        )
        # Revoke both rights on this (color, z, w) slice.
        self.castling_rights = frozenset(
            r for r in self.castling_rights if r[:3] != (king.color, z, w)
        )
        self.side_to_move = Color(1 - self.side_to_move)

    def pop(self) -> Move4D:
        """Undo the most recent :meth:`push`, restoring all game-level state.

        Returns the move that was undone (for castling, this is the
        king's move; the paired rook move is popped implicitly).

        Raises :class:`IndexError` if the undo stack is empty — the
        same failure mode as :meth:`Board4D.pop`.
        """
        undo_entry = self._undo.pop()
        if undo_entry.is_castling_compound:
            self.board.pop()  # rook move
            move = self.board.pop()  # king move
        else:
            move = self.board.pop()
        self.castling_rights = undo_entry.prior_castling_rights
        self.side_to_move = Color(1 - self.side_to_move)
        return move

    def legal_moves(self) -> Iterator[Move4D]:
        """Yield every legal move for ``side_to_move`` in the current state.

        Non-castling candidates use make-unmake on the underlying board:
        each pseudo-legal candidate is pushed, king-safety is checked,
        and the candidate is popped whether or not it's legal.

        Castling candidates are enumerated from :attr:`castling_rights`
        and validated via a full :meth:`push` / :meth:`pop` round-trip
        — this reuses all of :meth:`_push_castling`'s preconditions
        without duplicating them.

        The board is bit-identical before and after iteration (assuming
        the caller does not mutate it mid-iteration).
        """
        candidates = list(_all_pseudo_legal_moves(self.side_to_move, self.board))
        for move in candidates:
            self.board.push(move)
            safe = not any_king_attacked(self.side_to_move, self.board)
            self.board.pop()
            if safe:
                yield move
        yield from self._castling_candidates()

    def _castling_candidates(self) -> Iterator[Move4D]:
        """Yield fully-legal castling moves for ``side_to_move``.

        Each candidate is trial-pushed via :meth:`push`; if every §3.9
        Def 10 precondition holds, the move is popped and yielded.
        """
        for right in self.castling_rights:
            color, z, w, side = right
            if color != self.side_to_move:
                continue
            back_y = 0 if color is Color.WHITE else BOARD_SIZE - 1
            from_sq = Square4D(4, back_y, z, w)
            to_x = 6 if side is CastleSide.KINGSIDE else 2
            to_sq = Square4D(to_x, back_y, z, w)
            move = Move4D(from_sq, to_sq, is_castling=True)
            try:
                self.push(move)
            except IllegalMoveError:
                continue
            self.pop()
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
