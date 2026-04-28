"""Native (C) encoder integration tests — chess-spectral 1.3.2+.

The native binary lives at ``chess_spectral/_native/spectral_4d{.exe?}``
inside chess-spectral's platform wheels. Our adapter
:mod:`chess4d.native_encoder` translates chess4d's NDJSON sidecars
into the upstream NDJSON4 schema and shells out to that binary.

These tests cover:

* Module-level discovery (``locate_native_binary``).
* FEN4 v1 round-trip parity against ``chess_spectral.fen_4d.parse``.
* End-to-end NDJSON → spectralz parity between the Python encoder
  and the native binary on a real corpus. Bytes don't match
  exactly — the Python path produces ~``2^-55`` accumulation noise
  in the A_1 channel that the C path zeros out — but the encodings
  agree to well within float32 precision.

Skipped as a module when the ``chess_spectral`` extra isn't
installed *or* when the bundled native binary isn't present (pure-
Python ``py3-none-any`` fallback wheel). Both gates are intentional:
``--encoder native`` is a runtime-discoverable feature, not a
build-time guarantee.
"""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

pytest.importorskip("chess_spectral")

from chess4d import initial_position
from chess4d.corpus import (
    _pos4_compact,
    encode_existing_run,
    encode_ndjson_to_spectralz,
    generate_corpus,
)
from chess4d.native_encoder import (
    NativeEncoderUnavailable,
    encode_ndjson_via_native,
    locate_native_binary,
    pos4_to_fen4,
)

_NATIVE_BINARY = locate_native_binary()
pytestmark = pytest.mark.skipif(
    _NATIVE_BINARY is None,
    reason="no bundled chess-spectral native binary on this platform",
)


# 1. discovery + FEN4 serializer --------------------------------------------


def test_locate_native_binary_returns_path() -> None:
    p = locate_native_binary()
    assert p is not None
    assert p.is_file()
    assert p.name.startswith("spectral_4d")


def test_pos4_to_fen4_round_trip_initial_position() -> None:
    """pos4 → FEN4 string → parse() returns an equivalent dict."""
    from chess_spectral.fen_4d import parse

    pos4 = _pos4_compact(initial_position())
    fen4 = pos4_to_fen4(pos4)
    assert fen4.startswith("4d-fen v1:")
    parsed = parse(fen4)
    # Every chess4d square maps cleanly. Pawn values are 2-char
    # strings on our side, ``(color, axis)`` tuples on the parser
    # side — equivalent up to that representation difference.
    assert len(parsed) == len(pos4) == 896
    for k, v in pos4.items():
        idx = int(k)
        out = parsed[idx]
        if len(v) == 2:  # pawn
            assert out == (v[0], v[1])
        else:  # non-pawn single-char
            assert out == v


def test_pos4_to_fen4_empty_board() -> None:
    assert pos4_to_fen4({}) == "4d-fen v1:"


# 2. end-to-end native encode parity ----------------------------------------


def _generate_tiny_corpus(tmp: Path) -> Path:
    """Helper: generate a 1-game, 8-ply, no-encode corpus and return its NDJSON."""
    result = generate_corpus(
        n_games=1,
        max_plies=8,
        seed=0,
        output_dir=tmp,
        encode=False,
        run_id="parity",
    )
    return result.games[0].ndjson_path


def test_encode_ndjson_via_native_full_game(tmp_path: Path) -> None:
    """Native encode of a small game produces a valid v4 spectralz."""
    from chess_spectral.frame_4d import read_spectralz_v4

    nd = _generate_tiny_corpus(tmp_path)
    out = tmp_path / "native_full.spectralz"
    pivot, encoded_plies, nbytes = encode_ndjson_via_native(nd, out)
    assert pivot == 0
    assert encoded_plies == 8
    assert nbytes > 0

    header, frames = read_spectralz_v4(out)
    assert header.version == 4
    assert len(frames) == 9  # initial + 8 moves
    assert [f.ply for f in frames] == list(range(9))


def test_encode_ndjson_via_native_last_n(tmp_path: Path) -> None:
    """``last_n`` slices the encoded window and preserves absolute plies."""
    from chess_spectral.frame_4d import read_spectralz_v4

    nd = _generate_tiny_corpus(tmp_path)
    out = tmp_path / "native_tail.spectralz"
    pivot, encoded_plies, _ = encode_ndjson_via_native(nd, out, last_n=3)
    assert pivot == 5
    assert encoded_plies == 3

    _, frames = read_spectralz_v4(out)
    # 3 encoded moves + the pivot frame = 4 frames.
    assert [f.ply for f in frames] == [5, 6, 7, 8]


def test_python_native_parity_within_float32_precision(tmp_path: Path) -> None:
    """Python and native encoders agree to ~1e-9 / ~2^-30 worst-case.

    The Python path accumulates float32 noise in channel 0 (A_1
    orbit-mean) at ``2^-55`` magnitude that the C path zeros out.
    The other 10 channels are bit-identical. Net: encodings agree
    to well within float32 precision (epsilon ~= 1.19e-7).
    """
    from chess_spectral.frame_4d import read_spectralz_v4

    nd = _generate_tiny_corpus(tmp_path)
    py_out = tmp_path / "py.spectralz"
    nv_out = tmp_path / "nv.spectralz"

    encode_ndjson_to_spectralz(nd, py_out, use_native=False)
    encode_ndjson_via_native(nd, nv_out)

    _, py_frames = read_spectralz_v4(py_out)
    _, nv_frames = read_spectralz_v4(nv_out)
    assert len(py_frames) == len(nv_frames)

    max_diff = 0.0
    for a, b in zip(py_frames, nv_frames):
        diff = float(np.max(np.abs(a.encoding - b.encoding)))
        max_diff = max(max_diff, diff)
    # Generous tolerance: actual observed is ~2.78e-17, this is
    # 1e9× looser to keep the test resilient if upstream changes
    # accumulation order. Anything < float32 eps would also pass.
    assert max_diff < 1e-9, (
        f"Python vs native max abs diff {max_diff} exceeds 1e-9; "
        "this implies a real numerical difference, not just A_1 "
        "accumulation noise"
    )


def test_python_native_channels_other_than_A1_bit_identical(tmp_path: Path) -> None:
    """Channels 1–10 should be bit-identical Python vs native.

    Only the A_1 orbit-mean channel (channel 0, dims 0..4095) sees
    the accumulation-noise discrepancy. Pinning this guards against
    upstream regressions widening the parity gap to other channels.
    """
    from chess_spectral.frame_4d import read_spectralz_v4

    nd = _generate_tiny_corpus(tmp_path)
    py_out = tmp_path / "py.spectralz"
    nv_out = tmp_path / "nv.spectralz"
    encode_ndjson_to_spectralz(nd, py_out, use_native=False)
    encode_ndjson_via_native(nd, nv_out)
    _, py_frames = read_spectralz_v4(py_out)
    _, nv_frames = read_spectralz_v4(nv_out)

    for a, b in zip(py_frames, nv_frames):
        ch1plus_py = a.encoding[4096:]
        ch1plus_nv = b.encoding[4096:]
        assert np.array_equal(ch1plus_py, ch1plus_nv), (
            "channels 1-10 should be bit-identical between Python "
            "and native encoders"
        )


# 3. integration through corpus.py ------------------------------------------


def test_generate_corpus_use_native_true_path(tmp_path: Path) -> None:
    """``use_native=True`` opt-in path produces a valid corpus."""
    from chess_spectral.frame_4d import read_spectralz_v4

    result = generate_corpus(
        n_games=1,
        max_plies=4,
        seed=0,
        output_dir=tmp_path,
        encode=True,
        use_native=True,
        run_id="native",
    )
    assert result.games[0].encoding_path is not None
    _, frames = read_spectralz_v4(result.games[0].encoding_path)
    assert len(frames) == 5  # 4 moves + initial


def test_generate_corpus_use_native_false_uses_python(tmp_path: Path) -> None:
    """``use_native=False`` forces the Python encoder.

    We can't directly observe which encoder ran, but the spectralz
    bytes should match what a forced-Python retro-encode produces
    (and *not* what the native path produces, by the parity
    discussion above).
    """
    from chess_spectral.frame_4d import read_spectralz_v4

    result = generate_corpus(
        n_games=1,
        max_plies=4,
        seed=0,
        output_dir=tmp_path,
        encode=True,
        use_native=False,
        run_id="forced-python",
    )
    sz = result.games[0].encoding_path
    assert sz is not None
    _, frames = read_spectralz_v4(sz)
    # Python path: A_1 channel typically has tiny denormals from
    # accumulation. At least one element should be a tiny non-zero
    # in the A_1 slice across the encoded frames.
    has_tiny = any(
        np.any((np.abs(f.encoding[:4096]) > 0) & (np.abs(f.encoding[:4096]) < 1e-10))
        for f in frames
    )
    assert has_tiny, "Python path should produce tiny A_1 denormals"


def test_encode_existing_run_use_native(tmp_path: Path) -> None:
    """Retro-encode path honors ``use_native=True``."""
    from chess_spectral.frame_4d import read_spectralz_v4

    bare = generate_corpus(
        n_games=1,
        max_plies=4,
        seed=0,
        output_dir=tmp_path,
        encode=False,
        run_id="retro",
    )
    encode_existing_run(bare.run_dir, last_n=3, use_native=True)
    sz = bare.run_dir / "spectralz" / "game_001.spectralz"
    assert sz.exists()
    _, frames = read_spectralz_v4(sz)
    assert [f.ply for f in frames] == [1, 2, 3, 4]


# 4. error-path tests --------------------------------------------------------


def test_encode_ndjson_via_native_explicit_missing_binary(tmp_path: Path) -> None:
    """Passing a non-existent binary path raises NativeEncoderError-ish."""
    nd = _generate_tiny_corpus(tmp_path)
    out = tmp_path / "fail.spectralz"
    bogus = tmp_path / "definitely_not_a_real_binary.exe"
    with pytest.raises((FileNotFoundError, OSError)):
        encode_ndjson_via_native(nd, out, binary=bogus)


def test_use_native_true_with_no_binary_raises_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """``use_native=True`` with no binary in sight raises Unavailable."""
    monkeypatch.setattr(
        "chess4d.native_encoder.locate_native_binary",
        lambda: None,
    )
    nd = _generate_tiny_corpus(tmp_path)
    out = tmp_path / "no.spectralz"
    with pytest.raises(NativeEncoderUnavailable):
        encode_ndjson_via_native(nd, out)
