"""Phase 8 — chess-spectral adapter and spectralz v4 round-trip.

Skipped as a module when the ``spectral`` extra isn't installed. When
it is, these cover:

* pos4 translation: pawn tuple values, axis mapping, non-pawn chars
* single-position encoding smoke (shape / dtype / determinism)
* game replay counts (N+1 frames for N moves)
* spectralz v4 round-trip via :func:`read_spectralz_v4`
* tiny corpus reproducibility with a fixed seed
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytest.importorskip("chess_spectral")

import numpy as np

from chess4d import (
    Board4D,
    Color,
    GameState,
    Move4D,
    PawnAxis,
    Piece,
    PieceType,
    Square4D,
    initial_position,
)
from chess4d.corpus import generate_corpus
from chess4d.spectral import (
    ENCODING_DIM_4D,
    encode_game,
    encode_position,
    gamestate_to_pos4,
    write_spectralz,
)

from chess_spectral.frame_4d import read_spectralz_v4


# 4a. Position translation --------------------------------------------------


def test_initial_position_entry_count() -> None:
    gs = initial_position()
    pos4 = gamestate_to_pos4(gs)
    # Paper §3.3: 28 populated (z,w)-slices × 16 pieces per color × 2 colors.
    assert len(pos4) == 896


def test_initial_position_pawn_nonpawn_split() -> None:
    gs = initial_position()
    pos4 = gamestate_to_pos4(gs)
    pawns = [v for v in pos4.values() if isinstance(v, tuple)]
    nonpawns = [v for v in pos4.values() if isinstance(v, str)]
    assert len(pawns) == 448
    assert len(nonpawns) == 448


def test_pawn_values_are_tuples_not_chars() -> None:
    gs = initial_position()
    pos4 = gamestate_to_pos4(gs)
    for v in pos4.values():
        if isinstance(v, tuple):
            color_char, axis_char = v
            assert color_char in ("P", "p")
            assert axis_char in ("y", "w")


def test_nonpawn_chars_uppercase_for_white_lowercase_for_black() -> None:
    gs = initial_position()
    pos4 = gamestate_to_pos4(gs)
    # White back rank lives on y=0 (slice (3,3) is central); Black on y=7.
    white_rook = Square4D(0, 0, 3, 3)
    black_rook = Square4D(0, 7, 3, 3)
    wkey = (white_rook.x << 9) | (white_rook.y << 6) | (white_rook.z << 3) | white_rook.w
    bkey = (black_rook.x << 9) | (black_rook.y << 6) | (black_rook.z << 3) | black_rook.w
    assert pos4[wkey] == "R"
    assert pos4[bkey] == "r"


def test_w_oriented_pawn_maps_to_w_axis_char() -> None:
    board = Board4D()
    board.place(
        Square4D(3, 0, 3, 1),
        Piece(color=Color.WHITE, piece_type=PieceType.PAWN, pawn_axis=PawnAxis.W),
    )
    gs = GameState(board=board, side_to_move=Color.WHITE)
    pos4 = gamestate_to_pos4(gs)
    (value,) = pos4.values()
    assert value == ("P", "w")


def test_y_oriented_pawn_maps_to_y_axis_char() -> None:
    board = Board4D()
    board.place(
        Square4D(3, 1, 3, 3),
        Piece(color=Color.BLACK, piece_type=PieceType.PAWN, pawn_axis=PawnAxis.Y),
    )
    gs = GameState(board=board, side_to_move=Color.BLACK)
    pos4 = gamestate_to_pos4(gs)
    (value,) = pos4.values()
    assert value == ("p", "y")


def test_linear_index_bit_packing() -> None:
    # Hand-compute one square: (x=1, y=2, z=3, w=4)
    #   = (1<<9) | (2<<6) | (3<<3) | 4 = 512 + 128 + 24 + 4 = 668
    board = Board4D()
    board.place(
        Square4D(1, 2, 3, 4),
        Piece(color=Color.WHITE, piece_type=PieceType.KNIGHT),
    )
    gs = GameState(board=board, side_to_move=Color.WHITE)
    pos4 = gamestate_to_pos4(gs)
    assert pos4 == {668: "N"}


# 4b. Encoding smoke tests --------------------------------------------------


def test_encode_position_shape_and_dtype() -> None:
    vec = encode_position(initial_position())
    assert vec.shape == (ENCODING_DIM_4D,) == (45056,)
    assert vec.dtype == np.float32


def test_encode_position_nonzero() -> None:
    vec = encode_position(initial_position())
    assert float(np.abs(vec).sum()) > 0.0


def test_encode_position_deterministic() -> None:
    a = encode_position(initial_position())
    b = encode_position(initial_position())
    assert np.array_equal(a, b)


# 4c. Game replay -----------------------------------------------------------


def test_encode_game_empty_moves_yields_one_pair() -> None:
    pairs = list(encode_game(initial_position(), []))
    assert len(pairs) == 1
    state, enc = pairs[0]
    assert enc.shape == (45056,)
    # The caller-passed state must be untouched after deepcopy.
    assert state is not None


def test_encode_game_yields_n_plus_one_pairs() -> None:
    start = initial_position()
    # Two simple Y-pawn pushes on opposite sides of a central slice.
    m1 = Move4D(Square4D(0, 1, 3, 3), Square4D(0, 3, 3, 3))
    m2 = Move4D(Square4D(0, 6, 3, 3), Square4D(0, 4, 3, 3))
    pairs = list(encode_game(start, [m1, m2]))
    assert len(pairs) == 3
    for _, enc in pairs:
        assert enc.shape == (45056,)
        assert enc.dtype == np.float32


def test_encode_game_does_not_mutate_start() -> None:
    start = initial_position()
    before = gamestate_to_pos4(start)
    m = Move4D(Square4D(0, 1, 3, 3), Square4D(0, 3, 3, 3))
    list(encode_game(start, [m]))
    after = gamestate_to_pos4(start)
    assert before == after


# 4d. Spectralz v4 round-trip ----------------------------------------------


def test_write_spectralz_round_trip(tmp_path: Path) -> None:
    start = initial_position()
    moves = [
        Move4D(Square4D(0, 1, 3, 3), Square4D(0, 3, 3, 3)),
        Move4D(Square4D(0, 6, 3, 3), Square4D(0, 4, 3, 3)),
    ]
    path = tmp_path / "round_trip.spectralz"
    nbytes = write_spectralz(path, start, moves)
    assert nbytes > 0
    assert path.stat().st_size == nbytes

    header, frames = read_spectralz_v4(path)
    assert header.version == 4
    assert header.encoding_dim == 45056
    assert header.n_plies == len(moves) + 1
    assert len(frames) == len(moves) + 1

    # Each frame's encoding matches encode_position bit-exactly.
    expected = [enc for _, enc in encode_game(start, moves)]
    for frame, want in zip(frames, expected):
        assert np.array_equal(frame.encoding, want)


def test_write_spectralz_initial_frame_has_zero_move(tmp_path: Path) -> None:
    path = tmp_path / "init_frame.spectralz"
    write_spectralz(path, initial_position(), [])
    _, frames = read_spectralz_v4(path)
    assert len(frames) == 1
    f0 = frames[0]
    assert f0.ply == 0
    assert f0.from_sq == (0, 0, 0, 0)
    assert f0.to_sq == (0, 0, 0, 0)
    assert f0.promo == 0


def test_write_spectralz_base_ply_offset(tmp_path: Path) -> None:
    """``base_ply`` shifts every ``Frame4D.ply`` by a constant offset.

    This is the mechanism corpus.py uses to write tail-encoded files
    whose ``ply`` numbers match absolute positions in the full game.
    """
    start = initial_position()
    moves = [
        Move4D(Square4D(0, 1, 3, 3), Square4D(0, 3, 3, 3)),
        Move4D(Square4D(0, 6, 3, 3), Square4D(0, 4, 3, 3)),
    ]
    path = tmp_path / "offset.spectralz"
    write_spectralz(path, start, moves, base_ply=100)
    _, frames = read_spectralz_v4(path)
    assert [f.ply for f in frames] == [100, 101, 102]


# 4e. Corpus smoke ----------------------------------------------------------


def test_generate_corpus_produces_requested_files(tmp_path: Path) -> None:
    result = generate_corpus(
        n_games=3, max_plies=10, seed=42, output_dir=tmp_path
    )
    assert len(result.games) == 3
    assert (result.run_dir / "spectralz").is_dir()
    for s in result.games:
        assert s.c4d_path.exists()
        assert s.ndjson_path.exists()
        assert s.encoding_path is not None
        assert s.encoding_path.exists()
        assert s.encoding_bytes > 0
        header, _ = read_spectralz_v4(s.encoding_path)
        assert header.version == 4


def test_generate_corpus_is_reproducible_with_seed(tmp_path: Path) -> None:
    # Fixed run_id so manifest.generated_utc doesn't spuriously differ;
    # c4d / NDJSON / spectralz are the bytes we actually care about.
    ra = generate_corpus(
        n_games=3, max_plies=10, seed=42, output_dir=tmp_path / "a", run_id="fixed"
    )
    rb = generate_corpus(
        n_games=3, max_plies=10, seed=42, output_dir=tmp_path / "b", run_id="fixed"
    )
    for sa, sb in zip(ra.games, rb.games):
        assert sa.encoding_path is not None
        assert sb.encoding_path is not None
        assert sa.encoding_path.read_bytes() == sb.encoding_path.read_bytes()
        assert sa.c4d_path.read_bytes() == sb.c4d_path.read_bytes()
        assert sa.ndjson_path.read_bytes() == sb.ndjson_path.read_bytes()
