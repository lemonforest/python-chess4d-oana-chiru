"""Tests for :meth:`Board4D.push` / :meth:`Board4D.pop` with rook moves.

Citations refer to Oana & Chiru, *A Mathematical Framework for
Four-Dimensional Chess*, MDPI AppliedMath 6(3):48, 2026
(DOI 10.3390/appliedmath6030048).

Paper §3.4 defines ``s' = apply(m, s)`` but is silent on the precise
undo semantics; the invariant tested here is the engine-design contract
*"any legal sequence of pushes followed by the same number of pops
returns the board to a bit-identical prior state"*.
"""

from __future__ import annotations

import copy
import random

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from chess4d import BOARD_SIZE, Board4D, Color, Move4D, PawnAxis, PieceType, Piece, Square4D
from chess4d.errors import IllegalMoveError
from chess4d.pieces import rook_moves


def _white_rook() -> Piece:
    return Piece(color=Color.WHITE, piece_type=PieceType.ROOK)


def _black_rook() -> Piece:
    return Piece(color=Color.BLACK, piece_type=PieceType.ROOK)


def _white_pawn() -> Piece:
    return Piece(color=Color.WHITE, piece_type=PieceType.PAWN, pawn_axis=PawnAxis.Y)


def _board_snapshot(board: Board4D) -> dict[Square4D, Piece]:
    """Return a deep-copy of the placement dict (undo stack is excluded)."""
    return copy.deepcopy(board._squares)


# --- happy-path push ---------------------------------------------------------


def test_push_legal_rook_move_moves_piece() -> None:
    board = Board4D()
    from_sq = Square4D(0, 0, 0, 0)
    to_sq = Square4D(3, 0, 0, 0)
    board.place(from_sq, _white_rook())
    board.push(Move4D(from_sq, to_sq))
    assert board.occupant(from_sq) is None
    assert board.occupant(to_sq) == _white_rook()


def test_push_captures_opposing_piece() -> None:
    board = Board4D()
    from_sq = Square4D(0, 0, 0, 0)
    to_sq = Square4D(0, 5, 0, 0)
    board.place(from_sq, _white_rook())
    board.place(to_sq, _black_rook())
    board.push(Move4D(from_sq, to_sq))
    assert board.occupant(to_sq) == _white_rook()


# --- rejection paths --------------------------------------------------------


def test_push_empty_square_raises() -> None:
    board = Board4D()
    with pytest.raises(IllegalMoveError):
        board.push(Move4D(Square4D(0, 0, 0, 0), Square4D(1, 0, 0, 0)))


def test_push_non_rook_piece_raises_in_d2() -> None:
    """Deliverable 2 limitation: only rooks may move."""
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _white_pawn())
    with pytest.raises(IllegalMoveError):
        board.push(Move4D(Square4D(0, 0, 0, 0), Square4D(0, 1, 0, 0)))


def test_push_non_axis_move_raises() -> None:
    """A move changing two coordinates is not rook-reachable (Theorem 2)."""
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _white_rook())
    with pytest.raises(IllegalMoveError):
        board.push(Move4D(Square4D(0, 0, 0, 0), Square4D(1, 1, 0, 0)))


def test_push_onto_friendly_raises_and_leaves_board_unchanged() -> None:
    board = Board4D()
    from_sq = Square4D(0, 0, 0, 0)
    blocker = Square4D(3, 0, 0, 0)
    board.place(from_sq, _white_rook())
    board.place(blocker, _white_rook())
    snapshot = _board_snapshot(board)
    with pytest.raises(IllegalMoveError):
        board.push(Move4D(from_sq, blocker))
    assert _board_snapshot(board) == snapshot


def test_push_through_blocker_raises() -> None:
    board = Board4D()
    from_sq = Square4D(0, 0, 0, 0)
    board.place(from_sq, _white_rook())
    board.place(Square4D(2, 0, 0, 0), _black_rook())
    with pytest.raises(IllegalMoveError):
        # Attempt to leapfrog the black rook.
        board.push(Move4D(from_sq, Square4D(4, 0, 0, 0)))


# --- pop ---------------------------------------------------------------------


def test_pop_restores_simple_move() -> None:
    board = Board4D()
    from_sq = Square4D(0, 0, 0, 0)
    to_sq = Square4D(3, 0, 0, 0)
    board.place(from_sq, _white_rook())
    snapshot = _board_snapshot(board)
    move = Move4D(from_sq, to_sq)
    board.push(move)
    popped = board.pop()
    assert popped == move
    assert _board_snapshot(board) == snapshot


def test_pop_restores_captured_piece() -> None:
    board = Board4D()
    from_sq = Square4D(0, 0, 0, 0)
    to_sq = Square4D(0, 5, 0, 0)
    board.place(from_sq, _white_rook())
    board.place(to_sq, _black_rook())
    snapshot = _board_snapshot(board)
    board.push(Move4D(from_sq, to_sq))
    board.pop()
    assert _board_snapshot(board) == snapshot
    assert board.occupant(to_sq) == _black_rook()


def test_pop_on_empty_stack_raises() -> None:
    board = Board4D()
    with pytest.raises(IndexError):
        board.pop()


# --- hypothesis: bit-identical push/pop round-trip --------------------------


def _random_legal_rook_sequence(
    board: Board4D, rng: random.Random, max_length: int
) -> list[Move4D]:
    """Play a legal sequence of rook moves, alternating colors opportunistically."""
    played: list[Move4D] = []
    rooks_by_color: dict[Color, list[Square4D]] = {Color.WHITE: [], Color.BLACK: []}
    for sq, piece in board._squares.items():
        if piece.piece_type is PieceType.ROOK:
            rooks_by_color[piece.color].append(sq)

    for _ in range(max_length):
        # Pick a color that still has rooks.
        choices = [c for c, sqs in rooks_by_color.items() if sqs]
        if not choices:
            break
        color = rng.choice(choices)
        origin = rng.choice(rooks_by_color[color])
        candidate_moves = list(rook_moves(origin, color, board))
        if not candidate_moves:
            continue
        move = rng.choice(candidate_moves)
        captured = board.occupant(move.to_sq)
        board.push(move)
        played.append(move)

        # Maintain the index.
        rooks_by_color[color].remove(origin)
        rooks_by_color[color].append(move.to_sq)
        if captured is not None and captured.piece_type is PieceType.ROOK:
            rooks_by_color[captured.color].remove(move.to_sq)
    return played


def _populate_random_rooks(
    board: Board4D, rng: random.Random, count: int
) -> None:
    all_coords = [
        Square4D(x, y, z, w)
        for x in range(BOARD_SIZE) for y in range(BOARD_SIZE)
        for z in range(BOARD_SIZE) for w in range(BOARD_SIZE)
    ]
    chosen = rng.sample(all_coords, count)
    colors = [Color.WHITE, Color.BLACK]
    for sq in chosen:
        board.place(sq, Piece(color=rng.choice(colors), piece_type=PieceType.ROOK))


@given(
    seed=st.integers(min_value=0, max_value=10_000),
    piece_count=st.integers(min_value=1, max_value=12),
    move_count=st.integers(min_value=0, max_value=10),
)
@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
def test_push_then_pop_returns_bit_identical_state(
    seed: int, piece_count: int, move_count: int
) -> None:
    """Property: push a legal sequence, pop the same count, state is identical."""
    rng = random.Random(seed)
    board = Board4D()
    _populate_random_rooks(board, rng, piece_count)
    snapshot = _board_snapshot(board)

    played = _random_legal_rook_sequence(board, rng, move_count)
    for _ in played:
        board.pop()

    assert _board_snapshot(board) == snapshot
