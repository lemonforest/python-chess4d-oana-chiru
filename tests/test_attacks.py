"""Attack-map tests (paper §3.4, Definition 2; §3.10 Definition 13).

Citations refer to Oana & Chiru, *A Mathematical Framework for
Four-Dimensional Chess*, MDPI AppliedMath 6(3):48, 2026
(DOI 10.3390/appliedmath6030048).

These tests exercise the attack primitives in
:mod:`chess4d.legality` without going through ``GameState``, so a
regression in attack semantics is caught before the legality filter is
layered on top.

Pawn attack semantics are the subtle case: a pawn attacks its diagonal
capture squares regardless of whether those squares are empty, friendly,
or enemy (§3.10 Def 13). ``pawn_moves`` only emits diagonal moves when
the square holds an enemy, so the attack primitive must not route
through ``pawn_moves``.
"""

from __future__ import annotations

from chess4d import (
    Board4D,
    Color,
    PawnAxis,
    Piece,
    PieceType,
    Square4D,
    any_king_attacked,
    in_check,
    is_attacked,
    kings_of,
)


def _white(pt: PieceType) -> Piece:
    return Piece(Color.WHITE, pt)


def _black(pt: PieceType) -> Piece:
    return Piece(Color.BLACK, pt)


def _pawn(color: Color, axis: PawnAxis) -> Piece:
    return Piece(color, PieceType.PAWN, axis)


# --- rook attacks -----------------------------------------------------------


def test_rook_attacks_entire_axis_ray_on_empty_board() -> None:
    board = Board4D()
    board.place(Square4D(3, 3, 3, 3), _white(PieceType.ROOK))
    # Along +x: (4,3,3,3), (5,3,3,3), (6,3,3,3), (7,3,3,3) all attacked.
    for x in range(4, 8):
        assert is_attacked(Square4D(x, 3, 3, 3), Color.WHITE, board)
    # Along -x: (0..2,3,3,3).
    for x in range(0, 3):
        assert is_attacked(Square4D(x, 3, 3, 3), Color.WHITE, board)


def test_rook_attack_stops_at_friendly_blocker() -> None:
    """Blocker is a pawn so it does not itself contribute to the +x
    attack set, isolating the rook's truncation behavior."""
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _white(PieceType.ROOK))
    board.place(Square4D(3, 0, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    # Friendly blocker is not attacked by its own side's rook.
    assert not is_attacked(Square4D(3, 0, 0, 0), Color.WHITE, board)
    # Squares beyond the blocker are not attacked by the rook, and the
    # pawn (Y-axis) does not attack them either.
    assert not is_attacked(Square4D(4, 0, 0, 0), Color.WHITE, board)
    assert not is_attacked(Square4D(5, 0, 0, 0), Color.WHITE, board)


def test_rook_attack_terminates_at_enemy_blocker_and_captures_it() -> None:
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _white(PieceType.ROOK))
    board.place(Square4D(3, 0, 0, 0), _black(PieceType.ROOK))
    # Enemy blocker square IS attacked (capture terminates the ray).
    assert is_attacked(Square4D(3, 0, 0, 0), Color.WHITE, board)
    # Beyond the enemy is not attacked.
    assert not is_attacked(Square4D(4, 0, 0, 0), Color.WHITE, board)


# --- bishop attacks ---------------------------------------------------------


def test_bishop_attacks_planar_diagonal_on_empty_board() -> None:
    board = Board4D()
    board.place(Square4D(3, 3, 3, 3), _white(PieceType.BISHOP))
    # XY +/+ diagonal.
    assert is_attacked(Square4D(5, 5, 3, 3), Color.WHITE, board)
    # ZW -/- diagonal.
    assert is_attacked(Square4D(3, 3, 1, 1), Color.WHITE, board)


def test_bishop_never_attacks_opposite_parity_square() -> None:
    """Paper §3.7 Lemma 2: every bishop move preserves parity, so a
    square of opposite parity cannot be in its attack set."""
    board = Board4D()
    origin = Square4D(3, 3, 3, 3)  # parity 12 % 2 == 0
    board.place(origin, _white(PieceType.BISHOP))
    # A square of odd parity — cannot be attacked.
    odd_target = Square4D(3, 3, 3, 4)
    assert odd_target.parity() != origin.parity()
    assert not is_attacked(odd_target, Color.WHITE, board)


def test_bishop_friendly_blocker_truncates_diagonal() -> None:
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _white(PieceType.BISHOP))
    board.place(Square4D(3, 3, 0, 0), _white(PieceType.ROOK))
    # The XY-diagonal target past the blocker.
    assert not is_attacked(Square4D(4, 4, 0, 0), Color.WHITE, board)


def test_bishop_enemy_blocker_ends_ray_with_capture() -> None:
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _white(PieceType.BISHOP))
    board.place(Square4D(3, 3, 0, 0), _black(PieceType.ROOK))
    assert is_attacked(Square4D(3, 3, 0, 0), Color.WHITE, board)
    assert not is_attacked(Square4D(4, 4, 0, 0), Color.WHITE, board)


# --- queen attacks ----------------------------------------------------------


def test_queen_combines_rook_and_bishop_attacks() -> None:
    board = Board4D()
    board.place(Square4D(4, 4, 4, 4), _white(PieceType.QUEEN))
    # Rook-style 1-axis.
    assert is_attacked(Square4D(4, 4, 7, 4), Color.WHITE, board)
    # Bishop-style 2-axis (XY).
    assert is_attacked(Square4D(6, 6, 4, 4), Color.WHITE, board)


def test_queen_does_not_attack_3_axis_diagonal() -> None:
    """§3.8 Def 7: queen is restricted to 1- and 2-axis displacements."""
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _white(PieceType.QUEEN))
    # A 3-axis diagonal target — outside the queen's reach.
    assert not is_attacked(Square4D(2, 2, 2, 0), Color.WHITE, board)


# --- knight attacks ---------------------------------------------------------


def test_knight_attacks_leaper_target_ignoring_intermediate() -> None:
    board = Board4D()
    board.place(Square4D(2, 2, 2, 2), _white(PieceType.KNIGHT))
    # Intermediate squares don't matter.
    board.place(Square4D(3, 2, 2, 2), _black(PieceType.ROOK))
    # (+2, +1, 0, 0) from origin → (4, 3, 2, 2).
    assert is_attacked(Square4D(4, 3, 2, 2), Color.WHITE, board)


def test_knight_does_not_attack_through_friendly_on_target() -> None:
    board = Board4D()
    board.place(Square4D(2, 2, 2, 2), _white(PieceType.KNIGHT))
    board.place(Square4D(4, 3, 2, 2), _white(PieceType.ROOK))
    # Friendly target → knight doesn't attack it (can't capture).
    assert not is_attacked(Square4D(4, 3, 2, 2), Color.WHITE, board)


def test_knight_attacks_enemy_on_target() -> None:
    board = Board4D()
    board.place(Square4D(2, 2, 2, 2), _white(PieceType.KNIGHT))
    board.place(Square4D(4, 3, 2, 2), _black(PieceType.ROOK))
    assert is_attacked(Square4D(4, 3, 2, 2), Color.WHITE, board)


# --- king attacks -----------------------------------------------------------


def test_king_attacks_all_chebyshev_1_neighbors() -> None:
    board = Board4D()
    board.place(Square4D(3, 3, 3, 3), _white(PieceType.KING))
    # A few Chebyshev-1 neighbors (sampled).
    assert is_attacked(Square4D(4, 4, 4, 4), Color.WHITE, board)
    assert is_attacked(Square4D(2, 3, 3, 3), Color.WHITE, board)
    assert is_attacked(Square4D(3, 3, 4, 2), Color.WHITE, board)


def test_king_does_not_attack_beyond_chebyshev_1() -> None:
    board = Board4D()
    board.place(Square4D(3, 3, 3, 3), _white(PieceType.KING))
    assert not is_attacked(Square4D(5, 3, 3, 3), Color.WHITE, board)
    assert not is_attacked(Square4D(3, 5, 3, 3), Color.WHITE, board)


# --- pawn attacks (the risky case) ------------------------------------------


def test_y_pawn_does_not_attack_forward_square_even_when_empty() -> None:
    board = Board4D()
    board.place(Square4D(3, 2, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    assert not is_attacked(Square4D(3, 3, 0, 0), Color.WHITE, board)


def test_y_pawn_does_not_attack_forward_square_even_when_occupied() -> None:
    """§3.10 classical-chess alignment: pawns never capture forward."""
    board = Board4D()
    board.place(Square4D(3, 2, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    board.place(Square4D(3, 3, 0, 0), _black(PieceType.ROOK))
    assert not is_attacked(Square4D(3, 3, 0, 0), Color.WHITE, board)


def test_y_pawn_attacks_empty_diagonal_square() -> None:
    """Critical: attack on an empty diagonal — pawn_moves would NOT emit
    this, but the attack set must include it (§3.10 Def 13)."""
    board = Board4D()
    board.place(Square4D(3, 2, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    # Empty square on the +x diagonal.
    assert is_attacked(Square4D(4, 3, 0, 0), Color.WHITE, board)
    assert is_attacked(Square4D(2, 3, 0, 0), Color.WHITE, board)


def test_y_pawn_attacks_friendly_on_diagonal_square() -> None:
    board = Board4D()
    board.place(Square4D(3, 2, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    board.place(Square4D(4, 3, 0, 0), _white(PieceType.ROOK))
    # Friendly on diagonal is still an attacked square (defended).
    assert is_attacked(Square4D(4, 3, 0, 0), Color.WHITE, board)


def test_black_y_pawn_attacks_downward_diagonals() -> None:
    board = Board4D()
    board.place(Square4D(3, 5, 0, 0), _pawn(Color.BLACK, PawnAxis.Y))
    assert is_attacked(Square4D(2, 4, 0, 0), Color.BLACK, board)
    assert is_attacked(Square4D(4, 4, 0, 0), Color.BLACK, board)
    # Upward is NOT attacked.
    assert not is_attacked(Square4D(4, 6, 0, 0), Color.BLACK, board)


def test_w_pawn_attacks_in_xw_plane_not_xy_plane() -> None:
    board = Board4D()
    board.place(Square4D(3, 3, 0, 2), _pawn(Color.WHITE, PawnAxis.W))
    # XW diagonal (+x, +w).
    assert is_attacked(Square4D(4, 3, 0, 3), Color.WHITE, board)
    # XY diagonal — must NOT be attacked (wrong plane).
    assert not is_attacked(Square4D(4, 4, 0, 2), Color.WHITE, board)


def test_pawn_capture_boundary_clipped_at_x_zero() -> None:
    board = Board4D()
    board.place(Square4D(0, 2, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    # Off-board (-1, 3, 0, 0) — no attack there (doesn't exist).
    # On-board (+1, 3, 0, 0) — is attacked.
    assert is_attacked(Square4D(1, 3, 0, 0), Color.WHITE, board)


def test_pawn_capture_boundary_clipped_at_x_seven() -> None:
    board = Board4D()
    board.place(Square4D(7, 2, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    # Only -x diagonal exists.
    assert is_attacked(Square4D(6, 3, 0, 0), Color.WHITE, board)


def test_pawn_does_not_attack_beyond_forward_rank() -> None:
    """A pawn at y=6 attacks y=7 diagonals, not y=8 (off-board)."""
    board = Board4D()
    board.place(Square4D(3, 6, 0, 0), _pawn(Color.WHITE, PawnAxis.Y))
    assert is_attacked(Square4D(4, 7, 0, 0), Color.WHITE, board)
    # y=6 is not an attack — pawn doesn't attack sideways.
    assert not is_attacked(Square4D(4, 6, 0, 0), Color.WHITE, board)


# --- kings_of / in_check / any_king_attacked --------------------------------


def test_kings_of_empty_board() -> None:
    assert list(kings_of(Color.WHITE, Board4D())) == []


def test_kings_of_finds_all_kings_of_color() -> None:
    board = Board4D()
    squares = [Square4D(0, 0, 0, 0), Square4D(7, 7, 7, 7), Square4D(3, 3, 3, 3)]
    for sq in squares:
        board.place(sq, _white(PieceType.KING))
    board.place(Square4D(1, 0, 0, 0), _black(PieceType.KING))
    assert set(kings_of(Color.WHITE, board)) == set(squares)


def test_in_check_false_when_king_not_attacked() -> None:
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _white(PieceType.KING))
    board.place(Square4D(7, 7, 7, 7), _black(PieceType.KING))
    assert not in_check(Color.WHITE, board)
    assert not in_check(Color.BLACK, board)


def test_in_check_true_when_king_on_attacked_ray() -> None:
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _white(PieceType.KING))
    board.place(Square4D(5, 0, 0, 0), _black(PieceType.ROOK))
    assert in_check(Color.WHITE, board)


def test_in_check_false_when_attack_ray_blocked_by_friendly() -> None:
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _white(PieceType.KING))
    board.place(Square4D(3, 0, 0, 0), _white(PieceType.ROOK))
    board.place(Square4D(5, 0, 0, 0), _black(PieceType.ROOK))
    # The white rook blocks the enemy rook's ray; king is safe.
    assert not in_check(Color.WHITE, board)


def test_in_check_with_no_kings_is_false() -> None:
    """No kings ⇒ no king can be attacked; trivially false."""
    board = Board4D()
    board.place(Square4D(5, 0, 0, 0), _black(PieceType.ROOK))
    assert not in_check(Color.WHITE, board)


def test_any_king_attacked_multi_king_detects_any() -> None:
    """Remark 1 precursor: with multiple kings, the predicate is true
    if ANY of them is attacked."""
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _white(PieceType.KING))  # safe
    board.place(Square4D(3, 3, 3, 3), _white(PieceType.KING))  # attacked below
    board.place(Square4D(3, 7, 3, 3), _black(PieceType.ROOK))  # attacks (3,3,3,3) via y-ray
    assert any_king_attacked(Color.WHITE, board)


def test_any_king_attacked_false_when_all_safe() -> None:
    board = Board4D()
    board.place(Square4D(0, 0, 0, 0), _white(PieceType.KING))
    board.place(Square4D(7, 7, 7, 7), _white(PieceType.KING))
    board.place(Square4D(4, 4, 4, 4), _black(PieceType.BISHOP))
    # Bishop on even parity; white kings at (0,0,0,0) parity 0 and (7,7,7,7) parity 0.
    # But the bishop has no clear diagonal to either (different planes/offsets).
    # Easier: just verify false when kings are not on any attack path.
    # Place bishop somewhere it can't reach kings.
    assert not any_king_attacked(Color.WHITE, board)


def test_pawn_attack_defends_king_region() -> None:
    """A friendly pawn's diagonal attack squares count as defended
    territory for the other-color-king-safety question from the
    opponent's perspective."""
    board = Board4D()
    # Black pawn attacks (2, 4, 0, 0) and (4, 4, 0, 0) diagonally down-attacking.
    board.place(Square4D(3, 5, 0, 0), _pawn(Color.BLACK, PawnAxis.Y))
    # A white king on (4, 4, 0, 0) is in check from that pawn.
    board.place(Square4D(4, 4, 0, 0), _white(PieceType.KING))
    assert in_check(Color.WHITE, board)
