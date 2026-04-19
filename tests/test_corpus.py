"""Corpus generator — chess-maths-the-movie nested layout.

Each run lands in ``<output>/<run_id>/`` with four artifact kinds:

* ``manifest.json`` — run metadata + per-game rows.
* ``c4d/game_NNN.c4d`` — compact 4D move notation (always present).
* ``ndjson/game_NNN.ndjson`` — per-ply pos4 snapshots + moves
  (always present).
* ``spectralz/game_NNN.spectralz`` — 45 056-dim per-ply encoding
  (absent with ``--no-encode``; tail-only with ``--encode-last``).

The spectralz-writing branch needs ``chess_spectral``, so encoding
tests skip at module import when the extra is missing. The NDJSON /
manifest / ``--no-encode`` assertions run on a bare install via the
dedicated ``NoEncode`` suite at the bottom of the file.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from chess4d.corpus import (
    NDJSON_FORMAT_ID,
    CorpusResult,
    GameSummary,
    _auto_run_id,
    generate_corpus,
    main,
)
from chess4d.notation import read_game_file


# --- Helpers shared by encode / no-encode suites ---------------------------


def _read_ndjson_lines(path: Path) -> list[dict]:
    """Parse one NDJSON file into a list of records (preserves order)."""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _read_manifest(run_dir: Path) -> dict:
    """Load ``run_dir/manifest.json`` into a plain dict."""
    return json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))


# --- No-encode mode: runs without chess_spectral --------------------------


# These tests exercise the c4d / NDJSON / manifest paths only and do
# not need the spectral extra. They share tmp_path semantics with the
# encoded suite below.


def test_generate_corpus_creates_run_dir_without_encode(tmp_path: Path) -> None:
    result = generate_corpus(
        n_games=2,
        max_plies=8,
        seed=0,
        output_dir=tmp_path,
        encode=False,
    )
    assert isinstance(result, CorpusResult)
    assert result.run_dir.parent == tmp_path
    assert result.run_dir.is_dir()
    assert (result.run_dir / "c4d").is_dir()
    assert (result.run_dir / "ndjson").is_dir()
    assert not (result.run_dir / "spectralz").exists()
    assert result.manifest_path.exists()


def test_no_encode_game_summaries(tmp_path: Path) -> None:
    result = generate_corpus(
        n_games=2,
        max_plies=8,
        seed=0,
        output_dir=tmp_path,
        encode=False,
    )
    for s in result.games:
        assert isinstance(s, GameSummary)
        assert s.c4d_path.exists()
        assert s.ndjson_path.exists()
        assert s.encoding_path is None
        assert s.encoded_plies == 0
        assert s.pivot_ply == 0
        assert s.encoding_bytes == 0
        assert s.c4d_bytes > 0
        assert s.ndjson_bytes > 0


def test_c4d_roundtrips(tmp_path: Path) -> None:
    """c4d sidecar parses back to the same move list the generator produced."""
    result = generate_corpus(
        n_games=1, max_plies=8, seed=0, output_dir=tmp_path, encode=False
    )
    (s,) = result.games
    _, moves = read_game_file(s.c4d_path)
    assert len(moves) == s.plies


def test_encode_false_with_encode_last_raises(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="mutually exclusive"):
        generate_corpus(
            n_games=1,
            max_plies=4,
            seed=0,
            output_dir=tmp_path,
            encode=False,
            encode_last=2,
        )


def test_run_id_override(tmp_path: Path) -> None:
    result = generate_corpus(
        n_games=1,
        max_plies=4,
        seed=0,
        output_dir=tmp_path,
        encode=False,
        run_id="my-fixed-corpus",
    )
    assert result.run_id == "my-fixed-corpus"
    assert result.run_dir == tmp_path / "my-fixed-corpus"
    assert result.run_dir.is_dir()


def test_auto_run_id_has_stable_format() -> None:
    fixed_now = datetime(2026, 4, 19, 18, 3, 42, tzinfo=timezone.utc)
    assert _auto_run_id(42, now=fixed_now) == "corpus_20260419_180342_seed42"
    assert _auto_run_id(None, now=fixed_now) == "corpus_20260419_180342_unseeded"


def test_auto_run_id_used_by_default(tmp_path: Path) -> None:
    result = generate_corpus(
        n_games=1, max_plies=4, seed=7, output_dir=tmp_path, encode=False
    )
    assert result.run_id.startswith("corpus_")
    assert result.run_id.endswith("_seed7")
    # The run_dir's basename matches the returned run_id verbatim.
    assert result.run_dir.name == result.run_id


def test_ndjson_schema_headers_and_records(tmp_path: Path) -> None:
    """Line 1 is the format tag; line 2 is the game header; the rest
    are per-ply records whose count matches ``plies + 1``."""
    result = generate_corpus(
        n_games=1, max_plies=10, seed=0, output_dir=tmp_path, encode=False
    )
    (s,) = result.games
    records = _read_ndjson_lines(s.ndjson_path)
    assert records[0] == {"format": NDJSON_FORMAT_ID}
    game_header = records[1]
    assert game_header["type"] == "game_header"
    assert game_header["game"] == 0
    assert game_header["headers"]["n_plies"] == s.plies
    assert game_header["headers"]["seed"] == 0
    assert game_header["headers"]["termination"] == s.termination
    # One per-ply record per position (plies + 1, including ply 0).
    ply_records = records[2:]
    assert len(ply_records) == s.plies + 1
    # Plies are consecutive starting from 0.
    assert [r["ply"] for r in ply_records] == list(range(s.plies + 1))


def test_ndjson_ply0_has_no_move_fields(tmp_path: Path) -> None:
    result = generate_corpus(
        n_games=1, max_plies=4, seed=0, output_dir=tmp_path, encode=False
    )
    (s,) = result.games
    records = _read_ndjson_lines(s.ndjson_path)
    ply0 = records[2]
    assert ply0["ply"] == 0
    assert ply0["move_from"] is None
    assert ply0["move_to"] is None
    assert ply0["move_promo"] is None
    assert ply0["is_castling"] is False
    assert ply0["is_en_passant"] is False
    # Side to move at ply 0 is White.
    assert ply0["side_to_move"] == "WHITE"


def test_ndjson_pos4_initial_counts(tmp_path: Path) -> None:
    """The starting-position pos4 dict has 896 entries — 2-char pawn
    values and 1-char non-pawns, split 448/448 per the paper."""
    result = generate_corpus(
        n_games=1, max_plies=2, seed=0, output_dir=tmp_path, encode=False
    )
    (s,) = result.games
    records = _read_ndjson_lines(s.ndjson_path)
    pos4_ply0 = records[2]["pos4"]
    assert len(pos4_ply0) == 896
    pawns = [v for v in pos4_ply0.values() if len(v) == 2]
    nonpawns = [v for v in pos4_ply0.values() if len(v) == 1]
    assert len(pawns) == 448
    assert len(nonpawns) == 448
    # Pawn values are color+axis: P/p prefix, y/w suffix.
    for v in pawns:
        assert v[0] in ("P", "p")
        assert v[1] in ("y", "w")
    # Non-pawn chars are the Oana-Chiru set, uppercase == white.
    for v in nonpawns:
        assert v in ("K", "Q", "R", "B", "N", "k", "q", "r", "b", "n")


def test_ndjson_side_to_move_flips_each_ply(tmp_path: Path) -> None:
    result = generate_corpus(
        n_games=1, max_plies=6, seed=0, output_dir=tmp_path, encode=False
    )
    (s,) = result.games
    records = _read_ndjson_lines(s.ndjson_path)
    stm = [r["side_to_move"] for r in records[2:]]
    # Ply 0 → White to move; after each push, it flips.
    expected = ["WHITE" if i % 2 == 0 else "BLACK" for i in range(len(stm))]
    assert stm == expected


def test_manifest_has_required_top_level_keys(tmp_path: Path) -> None:
    result = generate_corpus(
        n_games=2, max_plies=6, seed=0, output_dir=tmp_path, encode=False
    )
    manifest = _read_manifest(result.run_dir)
    for key in (
        "generated_utc",
        "run_id",
        "source",
        "fetch_params",
        "tool_versions",
        "aggregates",
        "games",
    ):
        assert key in manifest, f"missing manifest key: {key}"
    assert manifest["source"] == "random_playout"
    assert manifest["run_id"] == result.run_id
    assert manifest["fetch_params"]["seed"] == 0
    assert manifest["fetch_params"]["encode"] is False
    assert manifest["fetch_params"]["encode_last"] is None
    assert manifest["aggregates"]["n_games"] == 2
    assert manifest["aggregates"]["n_encoded_games"] == 0
    assert manifest["tool_versions"]["python"].count(".") == 2


def test_manifest_games_block_matches_summaries_no_encode(tmp_path: Path) -> None:
    result = generate_corpus(
        n_games=2, max_plies=6, seed=0, output_dir=tmp_path, encode=False
    )
    manifest = _read_manifest(result.run_dir)
    rows = manifest["games"]
    assert len(rows) == len(result.games)
    for row, summary in zip(rows, result.games):
        assert row["stem"] == summary.stem
        assert row["c4d"] == f"c4d/{summary.stem}.c4d"
        assert row["ndjson"] == f"ndjson/{summary.stem}.ndjson"
        assert row["spectralz"] is None
        assert row["spectralz_bytes"] is None
        assert row["plies"] == summary.plies
        assert row["encoded_plies"] == 0
        assert row["pivot_ply"] == 0
        assert row["termination"] == summary.termination


def test_reported_byte_counts_match_on_disk_sizes(tmp_path: Path) -> None:
    """Manifest + GameSummary byte counts match ``Path.stat().st_size``.

    Regression guard: on Windows, ``Path.write_text`` translates
    ``\\n`` to ``\\r\\n``, so ``len(text.encode("utf-8"))`` is *not*
    the on-disk size. Corpus writers must return ``stat().st_size``.
    """
    result = generate_corpus(
        n_games=2, max_plies=8, seed=0, output_dir=tmp_path, encode=False
    )
    manifest = _read_manifest(result.run_dir)
    for row, summary in zip(manifest["games"], result.games):
        assert summary.c4d_bytes == summary.c4d_path.stat().st_size
        assert summary.ndjson_bytes == summary.ndjson_path.stat().st_size
        assert row["c4d_bytes"] == summary.c4d_path.stat().st_size
        assert row["ndjson_bytes"] == summary.ndjson_path.stat().st_size


def test_cli_no_encode(tmp_path: Path) -> None:
    rc = main(
        [
            "--n-games", "1",
            "--seed", "0",
            "--max-plies", "8",
            "--no-encode",
            "--output", str(tmp_path),
            "--run-id", "cli-no-encode",
        ]
    )
    assert rc == 0
    run_dir = tmp_path / "cli-no-encode"
    assert (run_dir / "manifest.json").exists()
    assert (run_dir / "c4d" / "game_001.c4d").exists()
    assert (run_dir / "ndjson" / "game_001.ndjson").exists()
    assert not (run_dir / "spectralz").exists()


def test_cli_no_encode_and_encode_last_are_mutually_exclusive(
    tmp_path: Path,
) -> None:
    with pytest.raises(SystemExit):
        main(
            [
                "--n-games", "1",
                "--seed", "0",
                "--max-plies", "8",
                "--no-encode",
                "--encode-last", "3",
                "--output", str(tmp_path),
            ]
        )


def test_game_summary_is_frozen(tmp_path: Path) -> None:
    """GameSummary remains a frozen dataclass (callers rely on immutability)."""
    result = generate_corpus(
        n_games=1, max_plies=4, seed=0, output_dir=tmp_path, encode=False
    )
    (s,) = result.games
    with pytest.raises(Exception):  # FrozenInstanceError or dataclasses.FrozenInstanceError
        s.plies = 999  # type: ignore[misc]


def test_corpus_result_is_frozen(tmp_path: Path) -> None:
    result = generate_corpus(
        n_games=1, max_plies=4, seed=0, output_dir=tmp_path, encode=False
    )
    with pytest.raises(Exception):
        result.run_id = "other"  # type: ignore[misc]


# --- Encoded-mode suite (requires chess_spectral) -------------------------


spectral = pytest.importorskip("chess_spectral")

from chess_spectral.frame_4d import read_spectralz_v4  # noqa: E402


def test_generate_corpus_writes_all_four_artifacts(tmp_path: Path) -> None:
    result = generate_corpus(
        n_games=2, max_plies=8, seed=0, output_dir=tmp_path
    )
    assert (result.run_dir / "spectralz").is_dir()
    for s in result.games:
        assert s.c4d_path.exists()
        assert s.ndjson_path.exists()
        assert s.encoding_path is not None
        assert s.encoding_path.exists()
        assert s.encoded_plies == s.plies
        assert s.pivot_ply == 0
        assert s.encoding_bytes > 0


def test_encode_last_tail_only(tmp_path: Path) -> None:
    """Tail encoding: spectralz carries the last N plies; c4d/NDJSON carry all."""
    # Use a seed/max_plies combo that reliably produces a full 20-ply game.
    result = generate_corpus(
        n_games=1,
        max_plies=20,
        seed=0,
        output_dir=tmp_path,
        encode_last=6,
    )
    (s,) = result.games
    assert s.plies == 20
    assert s.encoded_plies == 6
    assert s.pivot_ply == 14
    assert s.encoding_path is not None

    # c4d holds the full 20-move game.
    _, moves = read_game_file(s.c4d_path)
    assert len(moves) == 20

    # NDJSON also carries all 20 plies + ply 0.
    ndjson_records = _read_ndjson_lines(s.ndjson_path)
    assert len(ndjson_records) == 2 + 20 + 1  # format + game_header + 21 positions

    # Spectralz holds encoded_plies + 1 frames (sentinel + one per move).
    _, frames = read_spectralz_v4(s.encoding_path)
    assert len(frames) == s.encoded_plies + 1


def test_encode_last_absolute_ply_numbering(tmp_path: Path) -> None:
    """Tail frames carry absolute ply numbers that line up with c4d/NDJSON."""
    result = generate_corpus(
        n_games=1,
        max_plies=20,
        seed=0,
        output_dir=tmp_path,
        encode_last=6,
    )
    (s,) = result.games
    assert s.encoding_path is not None
    _, frames = read_spectralz_v4(s.encoding_path)
    pivot = s.pivot_ply
    assert [f.ply for f in frames] == list(range(pivot, pivot + s.encoded_plies + 1))


def test_encode_last_larger_than_game_encodes_all(tmp_path: Path) -> None:
    """Requesting a tail longer than the game encodes the whole thing."""
    result = generate_corpus(
        n_games=1,
        max_plies=8,
        seed=0,
        output_dir=tmp_path,
        encode_last=500,
    )
    (s,) = result.games
    assert s.encoded_plies == s.plies
    assert s.pivot_ply == 0
    assert s.encoding_path is not None
    _, frames = read_spectralz_v4(s.encoding_path)
    # First frame is the true starting position, so ply numbering begins at 0.
    assert frames[0].ply == 0
    assert len(frames) == s.plies + 1


def test_manifest_with_encoding(tmp_path: Path) -> None:
    result = generate_corpus(
        n_games=2,
        max_plies=20,
        seed=0,
        output_dir=tmp_path,
        encode_last=5,
    )
    manifest = _read_manifest(result.run_dir)
    assert manifest["fetch_params"]["encode"] is True
    assert manifest["fetch_params"]["encode_last"] == 5
    assert manifest["aggregates"]["n_encoded_games"] == 2
    for row, summary in zip(manifest["games"], result.games):
        assert row["spectralz"] == f"spectralz/{summary.stem}.spectralz"
        assert row["spectralz_bytes"] == summary.encoding_bytes
        assert row["encoded_plies"] == summary.encoded_plies
        assert row["pivot_ply"] == summary.pivot_ply


def test_cli_encode_last(tmp_path: Path) -> None:
    rc = main(
        [
            "--n-games", "1",
            "--seed", "0",
            "--max-plies", "20",
            "--encode-last", "5",
            "--output", str(tmp_path),
            "--run-id", "cli-encode-last",
        ]
    )
    assert rc == 0
    run_dir = tmp_path / "cli-encode-last"
    assert (run_dir / "manifest.json").exists()
    assert (run_dir / "c4d" / "game_001.c4d").exists()
    assert (run_dir / "ndjson" / "game_001.ndjson").exists()
    assert (run_dir / "spectralz" / "game_001.spectralz").exists()
    _, frames = read_spectralz_v4(run_dir / "spectralz" / "game_001.spectralz")
    assert len(frames) == 5 + 1  # encoded_plies + sentinel


def test_reproducible_under_fixed_seed(tmp_path: Path) -> None:
    """Same (n_games, max_plies, seed) → byte-identical c4d, NDJSON,
    and spectralz. ``run_id`` is overridden to isolate manifest drift
    (``generated_utc`` differs between runs by design)."""
    a_dir = tmp_path / "a"
    b_dir = tmp_path / "b"
    ra = generate_corpus(
        n_games=2, max_plies=12, seed=42, output_dir=a_dir, run_id="fixed"
    )
    rb = generate_corpus(
        n_games=2, max_plies=12, seed=42, output_dir=b_dir, run_id="fixed"
    )
    assert len(ra.games) == len(rb.games) == 2
    for sa, sb in zip(ra.games, rb.games):
        assert sa.c4d_path.read_bytes() == sb.c4d_path.read_bytes()
        assert sa.ndjson_path.read_bytes() == sb.ndjson_path.read_bytes()
        assert sa.encoding_path is not None
        assert sb.encoding_path is not None
        assert sa.encoding_path.read_bytes() == sb.encoding_path.read_bytes()
