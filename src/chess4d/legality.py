"""Attack-map primitives for multi-king legality (paper §3.4, Def 2-5).

This module provides the queries the legality pipeline needs, built on
the pseudo-legal piece generators from :mod:`chess4d.pieces`:

* :func:`is_attacked` — does ``by_color`` attack ``square``?
* :func:`kings_of` — enumerate ``color``'s kings.
* :func:`in_check` — is any ``color`` king attacked by the opponent?
* :func:`any_king_attacked` — batched form used by the legality filter.

The attack set of a piece (§3.4 Def 2: ``Att_P(s) = ⋃_{u ∈ Pieces_P}
pMoves(u, s)``) is the union of its pseudo-legal move destinations, with
one deliberate exception for pawns: pawns attack along their diagonal
capture squares regardless of whether those squares are currently
occupied (§3.10 Def 13). ``pawn_moves`` only emits diagonal targets that
hold an enemy, so using it as the attack set undercounts empty diagonal
squares and would fail pre-move attack queries (e.g. "is square q
defended?"). We therefore dispatch pawn attacks to :data:`PAWN_CAPTURES`
directly and use ``<piece>_moves`` destinations for everything else.

Multi-king semantics (§3.4, Remark 1). With multiple kings per side,
legality requires *every* friendly king to be safe after the move; it is
not enough that one of several threatened kings has been defended.
:func:`any_king_attacked` takes all kings into account in a single pass.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable, Iterator

from chess4d.geometry import PAWN_CAPTURES
from chess4d.pieces import (
    bishop_moves,
    king_moves,
    knight_moves,
    queen_moves,
    rook_moves,
)
from chess4d.types import Color, Move4D, Piece, PieceType, Square4D

if TYPE_CHECKING:
    from chess4d.board import Board4D


_SliderLeaperGen = Callable[[Square4D, Color, "Board4D"], Iterator[Move4D]]

_SLIDER_LEAPER_GENS: dict[PieceType, _SliderLeaperGen] = {
    PieceType.ROOK: rook_moves,
    PieceType.BISHOP: bishop_moves,
    PieceType.QUEEN: queen_moves,
    PieceType.KNIGHT: knight_moves,
    PieceType.KING: king_moves,
}
"""Dispatch from non-pawn :class:`PieceType` to its move generator.

Pawn is intentionally absent — see :func:`_attacks_from` for why it has
a separate attack source (:data:`PAWN_CAPTURES` rather than
``pawn_moves``).
"""


def _attacks_from(origin: Square4D, piece: Piece, board: "Board4D") -> Iterator[Square4D]:
    """Yield the squares ``piece`` (sitting on ``origin``) attacks.

    For sliders/leapers/king, the attacked set equals the destinations
    of their pseudo-legal move generator — friendly-blocker and
    ray-termination behavior already match paper's Def 2. Pawns are
    dispatched to :data:`PAWN_CAPTURES` directly so that *empty*
    diagonal capture squares are still reported as attacked (§3.10 Def
    13); the `pawn_moves` generator would omit those.
    """
    if piece.piece_type is PieceType.PAWN:
        assert piece.pawn_axis is not None  # guaranteed by Piece.__post_init__
        yield from PAWN_CAPTURES[(piece.color, piece.pawn_axis)][origin]
        return
    generator = _SLIDER_LEAPER_GENS[piece.piece_type]
    for move in generator(origin, piece.color, board):
        yield move.to_sq


def is_attacked(square: Square4D, by_color: Color, board: "Board4D") -> bool:
    """Return ``True`` iff any ``by_color`` piece attacks ``square``.

    Paper §3.4 Def 2: ``square ∈ Att_{by_color}(board)``. Short-circuits
    on the first attacker found; suitable for per-square queries. For
    the hot path of filtering pseudo-legal moves through "is any king
    attacked?", prefer :func:`any_king_attacked`, which amortizes the
    attacker enumeration across all friendly kings.
    """
    for origin, piece in board.pieces_of(by_color):
        for target in _attacks_from(origin, piece, board):
            if target == square:
                return True
    return False


def kings_of(color: Color, board: "Board4D") -> Iterator[Square4D]:
    """Yield every square holding a ``color`` king (paper §3.3).

    The initial position has 28 kings per side (§3.3); most positions
    carry fewer after captures, but never zero in a legal game.
    """
    for sq, piece in board.pieces_of(color):
        if piece.piece_type is PieceType.KING:
            yield sq


def in_check(color: Color, board: "Board4D") -> bool:
    """Return ``True`` iff any ``color`` king is attacked by the opponent.

    Paper §3.4 Def 4 generalizes single-king check to a quantifier over
    ``K_P(s)``: ``color`` is in check iff there exists a king of
    ``color`` that lies in ``Att_{1−color}(board)``.
    """
    return any_king_attacked(color, board)


def any_king_attacked(color: Color, board: "Board4D") -> bool:
    """Return ``True`` iff at least one ``color`` king is attacked.

    This is the legality filter's hot predicate: called once per
    pseudo-legal move during ``legal_moves`` generation. The
    implementation inverts the naive ``for king: for enemy: ...`` loop
    to a single enemy pass whose destinations are intersected against a
    precomputed ``frozenset`` of king squares — roughly
    ``O(enemies × mobility)`` rather than
    ``O(kings × enemies × mobility)``. At the 896-piece initial
    position, that drops a hot-path query from ~28 × 448 × 80 ≈ 1M ops
    to ~448 × 80 ≈ 36K ops.
    """
    king_squares: frozenset[Square4D] = frozenset(kings_of(color, board))
    if not king_squares:
        return False
    enemy = Color(1 - color)
    for origin, piece in board.pieces_of(enemy):
        for target in _attacks_from(origin, piece, board):
            if target in king_squares:
                return True
    return False
