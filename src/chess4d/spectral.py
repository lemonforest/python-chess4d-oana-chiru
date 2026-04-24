"""chess4d ⇄ chess-spectral adapter (Phase 8).

Bridges :class:`chess4d.GameState` into the ``chess_spectral`` 4D
encoder and the ``spectralz`` v4 frame format. The encoder itself lives
in the sibling mlehaptics repository and is installed via the optional
``[spectral]`` extra.

Three public entry points::

    gamestate_to_pos4(gs)        -> dict keyed by linear square index
    encode_position(gs)          -> (45056,) float32 numpy array
    encode_game(start, moves)    -> iterator of (GameState, ndarray)
    write_spectralz(path, ...)   -> int bytes written, spectralz v4

Pawn value convention follows the v1.1.1 Oana-Chiru schema documented
on :func:`chess_spectral.encoder_4d.encode_4d`: pawns are emitted as
``(color_char, axis_char)`` tuples, never as bare single chars (the
legacy form emits a ``DeprecationWarning`` and is avoided here).

Import drift note: the project spec references
``chess_spectral_4d.encode_4d`` and ``chess_spectral_4d.frame_4d``, but
in the v1.1.1 package layout ``chess_spectral_4d`` only re-exports
constants. The real encoder is ``chess_spectral.encoder_4d.encode_4d``
and the writer is ``chess_spectral.frame_4d.write_spectralz_v4``; those
are what this module imports.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import TYPE_CHECKING, Iterable, Iterator, Union

try:
    # chess-spectral ≥ 1.2.2 ships a ``py.typed`` marker; the
    # ``# type: ignore[import-untyped]`` comments the earlier pin
    # needed are now rejected by mypy as unused, so they're gone.
    from chess_spectral.encoder_4d import (
        ENCODING_DIM_4D,
        encode_4d,
    )
    from chess_spectral.frame_4d import (
        Frame4D,
        read_spectralz_v4,
        write_spectralz_v4,
    )
except ImportError as e:  # pragma: no cover — exercised only without extra
    raise ImportError(
        "chess4d.spectral requires the 'spectral' extra. "
        "Install with: pip install chess4d[spectral]"
    ) from e

from chess4d.state import GameState
from chess4d.types import Color, Move4D, PieceType, Square4D

if TYPE_CHECKING:
    import numpy as np


__all__ = [
    "ENCODING_DIM_4D",
    "Frame4D",
    "encode_game",
    "encode_position",
    "gamestate_to_pos4",
    "read_spectralz_v4",
    "write_spectralz",
]


PieceValue = Union[str, tuple[str, str]]

_NONPAWN_CHAR: dict[PieceType, str] = {
    PieceType.KNIGHT: "N",
    PieceType.BISHOP: "B",
    PieceType.ROOK: "R",
    PieceType.QUEEN: "Q",
    PieceType.KING: "K",
}


def _linear_index(sq: Square4D) -> int:
    """Encoder's linear square index: ``(x<<9) | (y<<6) | (z<<3) | w``.

    Matches the ordering used internally by :func:`encode_4d` to lay
    out the 4096 board squares across the 11 spectral channels.
    """
    return (sq.x << 9) | (sq.y << 6) | (sq.z << 3) | sq.w


def gamestate_to_pos4(gs: GameState) -> dict[int, PieceValue]:
    """Translate a :class:`GameState` into the encoder's ``pos4`` dict.

    Empty squares are omitted. Pawns are always emitted as
    ``(color_char, axis_char)`` tuples per the v1.1.1 Oana-Chiru
    schema; non-pawn pieces are single characters, uppercase for
    White and lowercase for Black.

    Raises :class:`ValueError` for a pawn without a ``pawn_axis`` (the
    :class:`~chess4d.types.Piece` invariant should make this
    unreachable) or for an unrecognized ``piece_type``.
    """
    pos4: dict[int, PieceValue] = {}
    for color in (Color.WHITE, Color.BLACK):
        uppercase = color is Color.WHITE
        for sq, piece in gs.board.pieces_of(color):
            key = _linear_index(sq)
            if piece.piece_type is PieceType.PAWN:
                if piece.pawn_axis is None:
                    raise ValueError(
                        f"Pawn at {sq} has no pawn_axis; cannot encode."
                    )
                color_char = "P" if uppercase else "p"
                axis_char = piece.pawn_axis.name.lower()
                pos4[key] = (color_char, axis_char)
                continue
            base = _NONPAWN_CHAR.get(piece.piece_type)
            if base is None:
                raise ValueError(
                    f"Unrecognized piece_type {piece.piece_type!r} at {sq}."
                )
            pos4[key] = base if uppercase else base.lower()
    return pos4


def encode_position(gs: GameState) -> "np.ndarray":
    """Encode a single :class:`GameState` as a ``(45056,)`` float32 vector."""
    result: "np.ndarray" = encode_4d(gamestate_to_pos4(gs))
    return result


def encode_game(
    start: GameState, moves: Iterable[Move4D]
) -> Iterator[tuple[GameState, "np.ndarray"]]:
    """Replay ``moves`` from ``start``, yielding ``(state, encoding)`` per ply.

    The initial state is yielded first (ply 0) and then once per
    applied move, giving ``len(moves) + 1`` pairs for a finite
    iterable. ``start`` is deep-copied up front; the caller's state
    object is left untouched.
    """
    current = copy.deepcopy(start)
    yield current, encode_position(current)
    for move in moves:
        current.push(move)
        yield current, encode_position(current)


def _move_to_coords(
    move: Move4D | None,
) -> tuple[tuple[int, int, int, int], tuple[int, int, int, int], int]:
    """Return ``(from_coord, to_coord, promo_int)`` for a :class:`Frame4D`.

    The sentinel for "no move" (used on the ply-0 frame) is the
    zero-tuple pair with ``promo=0``, which is the same pattern the
    spectralz writer uses internally when a frame is synthesized from
    an initial position.
    """
    if move is None:
        return (0, 0, 0, 0), (0, 0, 0, 0), 0
    promo = int(move.promotion) if move.promotion is not None else 0
    return (
        (move.from_sq.x, move.from_sq.y, move.from_sq.z, move.from_sq.w),
        (move.to_sq.x, move.to_sq.y, move.to_sq.z, move.to_sq.w),
        promo,
    )


def _move_flags(move: Move4D | None) -> int:
    """Pack ``is_castling`` and ``is_en_passant`` into the frame ``flags`` byte.

    Bit 0 = castling, bit 1 = en passant. The spectralz format reserves
    the full byte; higher bits are available for future semantics.
    """
    if move is None:
        return 0
    flags = 0
    if move.is_castling:
        flags |= 1 << 0
    if move.is_en_passant:
        flags |= 1 << 1
    return flags


def write_spectralz(
    path: str | Path,
    start: GameState,
    moves: Iterable[Move4D],
    *,
    base_ply: int = 0,
) -> int:
    """Encode a game and write it as a spectralz v4 file. Returns bytes written.

    The first frame is the ``start`` state with a zero-move sentinel;
    subsequent frames carry each applied move's geometry and flags.
    ``moves`` is consumed eagerly so the writer can report ``n_plies``
    in the header before streaming frames.

    ``base_ply`` offsets the ``Frame4D.ply`` values written to disk —
    the default of ``0`` keeps the legacy behavior where the first
    frame is labeled ply 0. Set ``base_ply`` to the absolute ply index
    of ``start`` when writing a tail-encoded file (e.g. pass
    ``base_ply=470`` when ``start`` is the state at absolute ply 470 of
    a longer game). The sidecar JSON written by
    :mod:`chess4d.corpus` carries the full move list, so analysis
    tooling can join the two via absolute ``ply`` numbers.
    """
    move_list = list(moves)
    frames: list[Frame4D] = []
    prev_move: Move4D | None = None
    for ply, (_, encoding) in enumerate(encode_game(start, move_list)):
        from_c, to_c, promo = _move_to_coords(prev_move)
        frames.append(
            Frame4D(
                encoding=encoding,
                ply=base_ply + ply,
                from_sq=from_c,
                to_sq=to_c,
                promo=promo,
                flags=_move_flags(prev_move),
            )
        )
        prev_move = move_list[ply] if ply < len(move_list) else None
    nbytes: int = write_spectralz_v4(path, frames)
    return nbytes
