"""Zobrist position hashing (paper §4.7).

A :class:`GameState` hash is the XOR of four independently-seeded
components:

* a bitstring for every ``(square, piece)`` combination, where
  ``piece`` carries ``color``, ``piece_type``, and (for pawns) the
  ``pawn_axis`` — so a Y-pawn and a W-pawn on the same square hash
  differently and promotion's placement change is visible in the hash;
* a single side-to-move bitstring, XORed in iff black is to move;
* a bitstring per :data:`~chess4d.types.CastlingRight`, XORed in for
  every right currently held;
* a bitstring per :class:`~chess4d.types.Square4D`, XORed in iff an
  en-passant target is set at that square.

The halfmove clock is deliberately **not** part of the hash — threefold
repetition compares placements, not clocks (paper §4.7 inherits FIDE's
repetition rule, which ignores the 50-move clock).

Tables are built once at import time from a fixed seed
(:data:`_SEED`) so hashes are stable across processes and across runs.
The library uses the naive ``O(pieces)`` hash here; an incremental
``O(1)`` hash maintained on :meth:`GameState.push`/``.pop`` is deferred
to Phase 6.
"""

from __future__ import annotations

from random import Random
from typing import TYPE_CHECKING

from chess4d.types import (
    BOARD_SIZE,
    CastleSide,
    CastlingRight,
    Color,
    PawnAxis,
    Piece,
    PieceType,
    Square4D,
)

if TYPE_CHECKING:
    from chess4d.state import GameState


_SEED: int = 0x4D_CE55_20_26
"""Fixed seed for Zobrist tables.

Hex-coded for easy visual recognition (``4D CE55 20 26`` — "4D ches5
2026", with the ``H`` dropped since it isn't a hex digit). The specific
value has no mathematical meaning beyond being a fixed bit pattern that
produces well-distributed 64-bit draws through Python's
Mersenne-Twister-backed :class:`random.Random`.
"""


def _piece_variants() -> list[Piece]:
    """Enumerate every distinct :class:`Piece` identity.

    14 variants total: ``2 colors × 5 non-pawn types`` plus
    ``2 colors × 2 pawn axes``. Iteration order is fixed (``Color``
    and ``PieceType`` enum order, then ``PawnAxis`` enum order) so the
    Zobrist seed produces the same per-piece bitstring every run.
    """
    variants: list[Piece] = []
    for color in Color:
        for pt in PieceType:
            if pt is PieceType.PAWN:
                for axis in PawnAxis:
                    variants.append(Piece(color, pt, axis))
            else:
                variants.append(Piece(color, pt))
    return variants


def _build_tables() -> tuple[
    dict[tuple[Square4D, Piece], int],
    int,
    dict[CastlingRight, int],
    dict[Square4D, int],
]:
    """Draw all Zobrist bitstrings in a fixed order.

    The draw order — pieces (``x, y, z, w, piece`` nested), then the
    side bit, then castling rights (``color, z, w, side`` nested), then
    en-passant squares (``x, y, z, w``) — is part of the seed contract.
    Changing it changes every hash the library produces, so future
    changes should bump the seed alongside the reorder.
    """
    rng = Random(_SEED)
    variants = _piece_variants()
    piece_hashes: dict[tuple[Square4D, Piece], int] = {}
    for x in range(BOARD_SIZE):
        for y in range(BOARD_SIZE):
            for z in range(BOARD_SIZE):
                for w in range(BOARD_SIZE):
                    sq = Square4D(x, y, z, w)
                    for piece in variants:
                        piece_hashes[(sq, piece)] = rng.getrandbits(64)
    side_hash = rng.getrandbits(64)
    castling_hashes: dict[CastlingRight, int] = {}
    for color in Color:
        for z in range(BOARD_SIZE):
            for w in range(BOARD_SIZE):
                for side in CastleSide:
                    castling_hashes[(color, z, w, side)] = rng.getrandbits(64)
    ep_hashes: dict[Square4D, int] = {}
    for x in range(BOARD_SIZE):
        for y in range(BOARD_SIZE):
            for z in range(BOARD_SIZE):
                for w in range(BOARD_SIZE):
                    ep_hashes[Square4D(x, y, z, w)] = rng.getrandbits(64)
    return piece_hashes, side_hash, castling_hashes, ep_hashes


_PIECE_HASHES, _SIDE_HASH, _CASTLING_HASHES, _EP_HASHES = _build_tables()


def hash_position(gs: "GameState") -> int:
    """Return the 64-bit Zobrist hash of ``gs``.

    Two :class:`GameState` instances have equal hashes iff they agree
    on piece placement (including pawn axes), side-to-move, castling
    rights, and en-passant target. The halfmove clock, position
    history, and undo stack are deliberately excluded — they do not
    affect position identity for repetition purposes.
    """
    h = 0
    for color in Color:
        for sq, piece in gs.board.pieces_of(color):
            h ^= _PIECE_HASHES[(sq, piece)]
    if gs.side_to_move is Color.BLACK:
        h ^= _SIDE_HASH
    for right in gs.castling_rights:
        h ^= _CASTLING_HASHES[right]
    if gs.ep_target is not None:
        h ^= _EP_HASHES[gs.ep_target]
    return h
