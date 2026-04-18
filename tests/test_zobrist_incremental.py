"""Phase 6B: incremental Zobrist hash invariant.

Covers: ``GameState._incremental_hash`` equals the full-recomputation
:func:`~chess4d.zobrist.hash_position` result after every push and
every pop, across every move type the engine supports.

Strategy:

* A deterministic scripted sequence exercises each move category at
  least once (ordinary, capture, two-step, en-passant, promotion,
  both-color both-side castling).
* A Hypothesis property test walks random push-pop paths from
  representative starting positions — the invariant must hold at
  every intermediate state.

The existing :func:`~chess4d.zobrist.hash_position` call in the full
recomputation path is the authoritative oracle. A divergence between
it and the incremental field is a correctness bug that would silently
break threefold repetition.
"""

from __future__ import annotations

import random

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from chess4d import (
    Board4D,
    CastleSide,
    Color,
    GameState,
    IllegalMoveError,
    Move4D,
    PawnAxis,
    Piece,
    PieceType,
    Square4D,
    hash_position,
    initial_position,
)


def _white(pt: PieceType) -> Piece:
    return Piece(Color.WHITE, pt)


def _black(pt: PieceType) -> Piece:
    return Piece(Color.BLACK, pt)


def _king(color: Color) -> Piece:
    return Piece(color, PieceType.KING)


def _pawn(color: Color, axis: PawnAxis) -> Piece:
    return Piece(color, PieceType.PAWN, axis)


def _assert_invariant(state: GameState, label: str = "") -> None:
    full = hash_position(state)
    assert state._incremental_hash == full, (
        f"incremental hash diverged from full at {label!r}: "
        f"incremental=0x{state._incremental_hash:016x} "
        f"full=0x{full:016x}"
    )


# --- deterministic scripted coverage ---------------------------------------


def test_invariant_on_initial_position_seed() -> None:
    """__post_init__ seeds the incremental hash correctly."""
    gs = initial_position()
    _assert_invariant(gs, "initial_position seed")


def test_invariant_after_ordinary_and_capture() -> None:
    """Ordinary move, then a capture; invariant holds at every step."""
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _king(Color.WHITE))
    board.place(Square4D(0, 7, 7, 7), _king(Color.BLACK))
    board.place(Square4D(4, 0, 0, 0), _white(PieceType.ROOK))
    board.place(Square4D(4, 4, 0, 0), _black(PieceType.ROOK))
    state = GameState(board=board, side_to_move=Color.WHITE)
    _assert_invariant(state, "pre-push")

    # Ordinary: white rook (4,0,0,0) → (4,3,0,0).
    state.push(Move4D(Square4D(4, 0, 0, 0), Square4D(4, 3, 0, 0)))
    _assert_invariant(state, "after ordinary push")
    # Capture: black rook (4,4,0,0) captures white rook.
    state.push(Move4D(Square4D(4, 4, 0, 0), Square4D(4, 3, 0, 0)))
    _assert_invariant(state, "after capture push")

    state.pop()
    _assert_invariant(state, "after capture pop")
    state.pop()
    _assert_invariant(state, "after ordinary pop")


def test_invariant_after_two_step_and_en_passant() -> None:
    """Two-step arms ep, opponent captures en passant; invariant all the way."""
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _king(Color.WHITE))
    board.place(Square4D(7, 7, 0, 0), _king(Color.BLACK))
    board.place(Square4D(3, 1, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    board.place(Square4D(4, 3, 0, 0), _pawn(Color.BLACK, PawnAxis.Y))
    state = GameState(board=board, side_to_move=Color.WHITE)
    _assert_invariant(state, "pre-push")

    # White two-step: (3,1) → (3,3) — arms ep_target (3,2).
    state.push(Move4D(Square4D(3, 1, 0, 0), Square4D(3, 3, 0, 0)))
    _assert_invariant(state, "after two-step")
    assert state.ep_target == Square4D(3, 2, 0, 0)

    # Black ep capture: (4,3) → (3,2), captures the white pawn at (3,3).
    state.push(
        Move4D(Square4D(4, 3, 0, 0), Square4D(3, 2, 0, 0), is_en_passant=True)
    )
    _assert_invariant(state, "after ep capture")

    state.pop()
    _assert_invariant(state, "after ep pop")
    state.pop()
    _assert_invariant(state, "after two-step pop")


def test_invariant_after_promotion() -> None:
    """Promotion (via capture, variety) keeps the invariant."""
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _king(Color.WHITE))
    board.place(Square4D(0, 7, 7, 7), _king(Color.BLACK))
    # White pawn one step from promotion on y-axis.
    board.place(Square4D(3, 6, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    # Black rook on promotion square — capture-promote.
    board.place(Square4D(4, 7, 0, 0), _black(PieceType.ROOK))
    state = GameState(board=board, side_to_move=Color.WHITE)
    _assert_invariant(state, "pre-push")

    state.push(
        Move4D(
            Square4D(3, 6, 0, 0),
            Square4D(4, 7, 0, 0),
            promotion=PieceType.QUEEN,
        )
    )
    _assert_invariant(state, "after capture-promotion push")

    state.pop()
    _assert_invariant(state, "after capture-promotion pop")


def _castle_fixture(color: Color, side: CastleSide, z: int, w: int) -> GameState:
    """Return a minimal position where ``color`` can castle ``side`` at slice (z, w)."""
    board = Board4D()
    back_y = 0 if color is Color.WHITE else 7
    other = Color(1 - color)
    other_y = 0 if other is Color.WHITE else 7
    other_slice = (0, 0) if (z, w) != (0, 0) else (7, 7)
    oz, ow = other_slice
    board.place(Square4D(4, back_y, z, w), _king(color))
    board.place(Square4D(0, back_y, z, w), Piece(color, PieceType.ROOK))
    board.place(Square4D(7, back_y, z, w), Piece(color, PieceType.ROOK))
    # Lone enemy king somewhere that can't attack.
    board.place(Square4D(4, other_y, oz, ow), _king(other))
    rights = frozenset({(color, z, w, side)})
    return GameState(board=board, side_to_move=color, castling_rights=rights)


def test_invariant_after_each_castling_variant() -> None:
    """Both colors, both sides — each keeps the incremental invariant."""
    for color in Color:
        for side in CastleSide:
            state = _castle_fixture(color, side, 0, 0)
            _assert_invariant(state, f"pre-castle {color.name} {side.name}")
            back_y = 0 if color is Color.WHITE else 7
            to_x = 6 if side is CastleSide.KINGSIDE else 2
            state.push(
                Move4D(
                    Square4D(4, back_y, 0, 0),
                    Square4D(to_x, back_y, 0, 0),
                    is_castling=True,
                )
            )
            _assert_invariant(state, f"after castle {color.name} {side.name}")
            state.pop()
            _assert_invariant(state, f"after un-castle {color.name} {side.name}")


def test_invariant_holds_on_illegal_move_rollback() -> None:
    """If a candidate push is rejected, the incremental hash is restored."""
    # Set up: white rook is pinned against its king; moving it exposes check.
    board = Board4D()
    board.place(Square4D(4, 0, 0, 0), _king(Color.WHITE))
    board.place(Square4D(4, 3, 0, 0), _white(PieceType.ROOK))
    board.place(Square4D(4, 7, 0, 0), _black(PieceType.QUEEN))
    board.place(Square4D(0, 7, 7, 7), _king(Color.BLACK))
    state = GameState(board=board, side_to_move=Color.WHITE)
    _assert_invariant(state, "pre illegal")

    prior_hash = state._incremental_hash
    try:
        # Sideways rook move — breaks the pin, would expose the king.
        state.push(Move4D(Square4D(4, 3, 0, 0), Square4D(0, 3, 0, 0)))
    except IllegalMoveError:
        pass
    # The incremental hash must equal its pre-attempt value.
    assert state._incremental_hash == prior_hash
    _assert_invariant(state, "post illegal rollback")


# --- property-based coverage ----------------------------------------------


def _random_walk(state: GameState, rng: random.Random, max_plies: int) -> int:
    """Push random legal moves, asserting invariant after each; return count."""
    pushed = 0
    for _ in range(max_plies):
        legal = list(state.legal_moves())
        if not legal:
            break
        state.push(rng.choice(legal))
        _assert_invariant(state, f"push #{pushed + 1}")
        pushed += 1
    return pushed


def _mid_game_state() -> GameState:
    """Small custom position with several piece types available."""
    board = Board4D()
    board.place(Square4D(4, 0, 0, 0), _king(Color.WHITE))
    board.place(Square4D(4, 7, 0, 0), _king(Color.BLACK))
    board.place(Square4D(0, 0, 0, 0), _white(PieceType.ROOK))
    board.place(Square4D(7, 0, 0, 0), _white(PieceType.ROOK))
    board.place(Square4D(3, 1, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    board.place(Square4D(4, 1, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    board.place(Square4D(5, 1, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    board.place(Square4D(3, 6, 0, 0), _pawn(Color.BLACK, PawnAxis.Y))
    board.place(Square4D(4, 6, 0, 0), _pawn(Color.BLACK, PawnAxis.Y))
    board.place(Square4D(2, 3, 0, 0), _black(PieceType.KNIGHT))
    return GameState(board=board, side_to_move=Color.WHITE)


@settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(seed=st.integers(min_value=0, max_value=2**32 - 1))
def test_invariant_on_random_push_pop_walks(seed: int) -> None:
    """Random legal-move walks keep the invariant push-and-pop symmetric."""
    state = _mid_game_state()
    _assert_invariant(state, "mid-game seed")
    rng = random.Random(seed)
    n_plies = rng.randint(2, 6)
    pushed = _random_walk(state, rng, n_plies)
    for i in range(pushed):
        state.pop()
        _assert_invariant(state, f"pop #{i + 1}")
