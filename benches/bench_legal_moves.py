"""Benchmark ``GameState.legal_moves()`` on representative positions.

Run::

    python benches/bench_legal_moves.py

Output: one line per scenario, median + max (ms) over N trials.

Not collected by pytest. This script is the measurement ruler every
sub-phase of Phase 6 is compared against. Scenarios are chosen to
stress different cost drivers:

* S1 initial position — primary target, 896 pieces, 2356 legal moves.
* S2 after one ply — verifies the first push doesn't create pathology.
* S3 mid-game (~200 pieces) — per-piece cost dominates, not fixed.
* S4 near-mate — legality filter hits the worst case.
* S5 single rook — fixed-overhead floor for a per-call measurement.

Also benchmarks ``push``/``pop`` cost so Phase 6B's incremental hash
change is visible even though it doesn't move the ``legal_moves`` needle.
"""

from __future__ import annotations

import random
import statistics
import time
from typing import Callable

from chess4d import (
    Board4D,
    CastleSide,
    CastlingRight,
    Color,
    GameState,
    IllegalMoveError,
    Move4D,
    PawnAxis,
    Piece,
    PieceType,
    Square4D,
    initial_position,
)


# --- scenario factories ----------------------------------------------------


def _initial_white() -> GameState:
    """S1: the Oana-Chiru starting position; white to move."""
    return initial_position()


def _after_one_ply() -> GameState:
    """S2: after one white ply. Black's legal moves are the target.

    Uses a pawn two-step from a corner slice that keeps the position
    far from any king-safety interaction. The first push exercises
    Board4D undo stack + GameState hash append.
    """
    gs = initial_position()
    # A corner-slice white pawn two-step: (0,1,0,0) → (0,3,0,0).
    gs.push(Move4D(Square4D(0, 1, 0, 0), Square4D(0, 3, 0, 0)))
    return gs


def _mid_game_thinned() -> GameState:
    """S3: start from the initial position, remove a deterministic
    ~700 pieces, leave ~200.

    Deterministic seed so the benchmark is reproducible across runs.
    Preserves every king so ``legal_moves`` still has a non-trivial
    king-safety filter to run. The remaining pieces are a mixed bag
    of pawns/rooks/knights/bishops/queens — representative of a
    middlegame density.
    """
    gs = initial_position()
    rng = random.Random(0xC0FFEE)
    all_coords = list(gs.board._squares.keys())
    all_coords.sort()
    rng.shuffle(all_coords)
    removed = 0
    target = 700
    for sq in all_coords:
        if removed >= target:
            break
        piece = gs.board.occupant(sq)
        if piece is None or piece.piece_type is PieceType.KING:
            continue
        gs.board.remove(sq)
        removed += 1
    # Clear castling rights — they depend on rook/king configuration that
    # we just perturbed, and we don't want castling-legality work to
    # dominate the measurement for this scenario.
    gs.castling_rights = frozenset()
    return gs


def _near_mate() -> GameState:
    """S4: near-mate position with a small piece count.

    Constructed on an otherwise empty board: one white king under
    attack by a black queen, one friendly piece capable of interposing
    or capturing. Exercises the legality filter under the condition
    it was designed for — ``in_check`` is true for most candidates.
    """
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), Piece(Color.WHITE, PieceType.KING))
    board.place(Square4D(4, 0, 0, 0), Piece(Color.BLACK, PieceType.QUEEN))
    board.place(Square4D(2, 0, 0, 0), Piece(Color.WHITE, PieceType.ROOK))
    board.place(Square4D(7, 7, 7, 7), Piece(Color.BLACK, PieceType.KING))
    return GameState(board=board, side_to_move=Color.WHITE)


def _single_rook() -> GameState:
    """S5: a single white rook on an empty board; white to move.

    No kings, so no king-safety filter; measures pure per-call
    overhead plus the rook's pseudo-legal generator.
    """
    board = Board4D()
    board.place(Square4D(3, 3, 3, 3), Piece(Color.WHITE, PieceType.ROOK))
    return GameState(board=board, side_to_move=Color.WHITE)


# --- harness ---------------------------------------------------------------


def bench_legal_moves(
    name: str, factory: Callable[[], GameState], n_trials: int = 5
) -> None:
    """Time ``legal_moves()`` over ``n_trials`` rebuilt positions."""
    times: list[float] = []
    move_count = 0
    for _ in range(n_trials):
        state = factory()
        t0 = time.perf_counter()
        moves = list(state.legal_moves())
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000)
        move_count = len(moves)
    median = statistics.median(times)
    p99 = max(times)
    print(
        f"{name:<48} median={median:8.1f}ms  max={p99:8.1f}ms  "
        f"moves={move_count}"
    )


def bench_push_pop(
    name: str, factory: Callable[[], GameState], n_trials: int = 5
) -> None:
    """Time a representative push+pop on a fresh state."""
    # A deterministic pseudo-legal move that exists in every scenario
    # having a white pawn at (0,1,*,*) — only the starting-position
    # variants. For non-starting factories, we skip.
    gs = factory()
    mv = Move4D(Square4D(0, 1, 0, 0), Square4D(0, 3, 0, 0))
    try:
        gs.push(mv)
        gs.pop()
    except (IllegalMoveError, KeyError):
        print(f"{name:<48} push-pop N/A (move illegal in this scenario)")
        return
    times: list[float] = []
    for _ in range(n_trials):
        state = factory()
        t0 = time.perf_counter()
        state.push(mv)
        state.pop()
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000)
    median = statistics.median(times)
    p99 = max(times)
    print(f"{name:<48} median={median:8.3f}ms  max={p99:8.3f}ms")


def main() -> None:
    print("=== legal_moves() ===")
    bench_legal_moves("S1 initial (white)", _initial_white)
    bench_legal_moves("S2 after 1 ply (black)", _after_one_ply)
    bench_legal_moves("S3 mid-game ~200 pieces", _mid_game_thinned)
    bench_legal_moves("S4 near-mate", _near_mate)
    bench_legal_moves("S5 single rook", _single_rook)
    print()
    print("=== push+pop ===")
    bench_push_pop("P1 initial position", _initial_white)


if __name__ == "__main__":
    main()
