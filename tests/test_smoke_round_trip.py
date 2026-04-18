"""End-of-Phase-3 smoke: a long mixed-piece push/pop round-trip.

Places one of every supported piece type, runs a scripted sequence of
pseudo-legal moves (including pawn promotions), then pops every move
and asserts bit-identical recovery of the initial position.

This exercises the ``_PIECE_GEOMETRY`` dispatch for sliders (rook,
bishop, queen) and leapers (knight, king), plus the dedicated
``_push_pawn`` branch with promotion, all sharing the refactored
3-tuple undo stack.
"""

from __future__ import annotations

from chess4d import (
    Board4D,
    Color,
    Move4D,
    PawnAxis,
    Piece,
    PieceType,
    Square4D,
)


def _board_snapshot(board: Board4D) -> dict[Square4D, Piece]:
    """Return the piece-placement mapping independent of undo-stack shape."""
    return {sq: board.occupant(sq) for sq in board._squares}  # noqa: SLF001


def test_mixed_piece_40_move_round_trip() -> None:
    board = Board4D()

    rook = Piece(Color.WHITE, PieceType.ROOK)
    bishop = Piece(Color.WHITE, PieceType.BISHOP)
    knight = Piece(Color.WHITE, PieceType.KNIGHT)
    king = Piece(Color.WHITE, PieceType.KING)
    queen = Piece(Color.WHITE, PieceType.QUEEN)
    white_pawn = Piece(Color.WHITE, PieceType.PAWN, PawnAxis.Y)
    black_w_pawn = Piece(Color.BLACK, PieceType.PAWN, PawnAxis.W)
    enemy_rook = Piece(Color.BLACK, PieceType.ROOK)

    placements: dict[Square4D, Piece] = {
        Square4D(0, 0, 0, 0): rook,
        Square4D(0, 0, 7, 0): bishop,
        Square4D(0, 0, 0, 7): knight,
        Square4D(7, 7, 7, 7): king,
        Square4D(4, 4, 4, 4): queen,
        Square4D(3, 6, 0, 0): white_pawn,    # one step from Y-promotion
        Square4D(7, 0, 0, 6): black_w_pawn,  # on W-pawn start rank
        Square4D(5, 0, 0, 0): enemy_rook,    # gets captured by rook
    }
    for sq, p in placements.items():
        board.place(sq, p)

    snapshot_before = _board_snapshot(board)

    moves: list[Move4D] = [
        # Rook: 1-axis slides, starting with a capture.
        Move4D(Square4D(0, 0, 0, 0), Square4D(5, 0, 0, 0)),  # captures enemy rook
        Move4D(Square4D(5, 0, 0, 0), Square4D(5, 3, 0, 0)),
        Move4D(Square4D(5, 3, 0, 0), Square4D(5, 3, 6, 0)),
        Move4D(Square4D(5, 3, 6, 0), Square4D(5, 3, 6, 4)),
        Move4D(Square4D(5, 3, 6, 4), Square4D(1, 3, 6, 4)),
        # Bishop: 2-axis planar diagonals across five different planes.
        Move4D(Square4D(0, 0, 7, 0), Square4D(3, 3, 7, 0)),   # XY
        Move4D(Square4D(3, 3, 7, 0), Square4D(3, 3, 5, 2)),   # ZW
        Move4D(Square4D(3, 3, 5, 2), Square4D(5, 3, 5, 4)),   # XW
        Move4D(Square4D(5, 3, 5, 4), Square4D(5, 0, 2, 4)),   # YZ
        Move4D(Square4D(5, 0, 2, 4), Square4D(3, 0, 0, 4)),   # XZ
        # Knight: 48-permutation leaper displacements.
        Move4D(Square4D(0, 0, 0, 7), Square4D(2, 1, 0, 7)),   # (+2,+1,0,0)
        Move4D(Square4D(2, 1, 0, 7), Square4D(0, 2, 0, 7)),   # (-2,+1,0,0)
        Move4D(Square4D(0, 2, 0, 7), Square4D(2, 3, 0, 7)),   # (+2,+1,0,0)
        Move4D(Square4D(2, 3, 0, 7), Square4D(2, 3, 2, 6)),   # (0,0,+2,-1)
        Move4D(Square4D(2, 3, 2, 6), Square4D(4, 3, 2, 5)),   # (+2,0,0,-1)
        # King: Chebyshev-1 steps, including diagonal pairs.
        Move4D(Square4D(7, 7, 7, 7), Square4D(6, 6, 6, 6)),   # (-1,-1,-1,-1)
        Move4D(Square4D(6, 6, 6, 6), Square4D(5, 5, 5, 5)),
        Move4D(Square4D(5, 5, 5, 5), Square4D(5, 5, 5, 6)),
        Move4D(Square4D(5, 5, 5, 6), Square4D(6, 5, 5, 6)),
        Move4D(Square4D(6, 5, 5, 6), Square4D(7, 4, 5, 6)),   # (+1,-1,0,0)
        # Queen: mix of 1-axis and 2-axis moves, across several planes.
        Move4D(Square4D(4, 4, 4, 4), Square4D(4, 4, 4, 0)),   # W rook-style
        Move4D(Square4D(4, 4, 4, 0), Square4D(4, 0, 0, 0)),   # YZ bishop-style
        Move4D(Square4D(4, 0, 0, 0), Square4D(0, 4, 0, 0)),   # XY bishop-style
        Move4D(Square4D(0, 4, 0, 0), Square4D(3, 4, 0, 0)),   # X rook-style
        Move4D(Square4D(3, 4, 0, 0), Square4D(3, 4, 3, 3)),   # ZW bishop-style
        # White Y-pawn promotion, then the promoted queen slides.
        Move4D(Square4D(3, 6, 0, 0), Square4D(3, 7, 0, 0), promotion=PieceType.QUEEN),
        Move4D(Square4D(3, 7, 0, 0), Square4D(3, 7, 4, 0)),
        Move4D(Square4D(3, 7, 4, 0), Square4D(3, 3, 0, 0)),
        Move4D(Square4D(3, 3, 0, 0), Square4D(3, 3, 0, 3)),
        # Black W-pawn: two-step, one-steps, then promotion to queen at w=0.
        Move4D(Square4D(7, 0, 0, 6), Square4D(7, 0, 0, 4)),
        Move4D(Square4D(7, 0, 0, 4), Square4D(7, 0, 0, 3)),
        Move4D(Square4D(7, 0, 0, 3), Square4D(7, 0, 0, 2)),
        Move4D(Square4D(7, 0, 0, 2), Square4D(7, 0, 0, 1)),
        Move4D(Square4D(7, 0, 0, 1), Square4D(7, 0, 0, 0), promotion=PieceType.QUEEN),
        # More rook slides to pad move count and mix axes further.
        Move4D(Square4D(1, 3, 6, 4), Square4D(1, 3, 6, 0)),
        Move4D(Square4D(1, 3, 6, 0), Square4D(1, 3, 0, 0)),
        # More king and knight shuffles.
        Move4D(Square4D(7, 4, 5, 6), Square4D(7, 5, 5, 7)),
        Move4D(Square4D(7, 5, 5, 7), Square4D(7, 6, 6, 7)),
        Move4D(Square4D(4, 3, 2, 5), Square4D(6, 4, 2, 5)),
        Move4D(Square4D(6, 4, 2, 5), Square4D(4, 5, 2, 5)),
    ]
    assert len(moves) >= 40, f"smoke needs at least 40 moves, got {len(moves)}"

    for move in moves:
        board.push(move)

    assert _board_snapshot(board) != snapshot_before

    for _ in moves:
        board.pop()

    snapshot_after = _board_snapshot(board)
    assert snapshot_after == snapshot_before
