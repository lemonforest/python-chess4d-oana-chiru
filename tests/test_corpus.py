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
    encode_existing_run,
    encode_main,
    encode_ndjson_to_spectralz,
    generate_corpus,
    main,
    read_ndjson_game,
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


def test_manifest_tool_versions_includes_chess4d(tmp_path: Path) -> None:
    """``tool_versions.chess4d`` is populated from the installed wheel.

    Regression guard: the dist name is ``python-chess4d-oana-chiru``,
    not ``chess4d``, so a naive ``version("chess4d")`` call raises
    ``PackageNotFoundError`` and silently drops the field. The manifest
    must look up the correct dist but keep the short key stable for
    downstream consumers.
    """
    result = generate_corpus(
        n_games=1, max_plies=4, seed=0, output_dir=tmp_path, encode=False
    )
    manifest = _read_manifest(result.run_dir)
    assert "chess4d" in manifest["tool_versions"]
    # Looks like a dotted semver (e.g. "0.2.0" or "0.2.0.dev3").
    assert manifest["tool_versions"]["chess4d"].count(".") >= 2


def test_read_ndjson_game_round_trips_moves(tmp_path: Path) -> None:
    """write_ndjson_game → read_ndjson_game recovers the exact move list.

    NDJSON is the bridge the encoder pass runs off of, so moves must
    round-trip byte-for-field: all five :class:`Move4D` fields (from,
    to, promotion, is_castling, is_en_passant) survive serialization.
    """
    result = generate_corpus(
        n_games=1, max_plies=12, seed=5, output_dir=tmp_path, encode=False
    )
    (s,) = result.games
    # c4d is the authoritative move list from the playout.
    _, original_moves = read_game_file(s.c4d_path)
    # Now read back via the NDJSON reader.
    start, moves, headers = read_ndjson_game(s.ndjson_path)
    assert moves == original_moves
    assert headers["n_plies"] == len(original_moves)
    assert headers["termination"] == s.termination
    assert headers["seed"] == 5
    # Start is the canonical initial position (the reader enforces this).
    from chess4d import initial_position
    assert start.side_to_move == initial_position().side_to_move


def test_read_ndjson_game_rejects_wrong_format(tmp_path: Path) -> None:
    """The reader refuses non-chess4d-ndjson-v1 files."""
    bad = tmp_path / "bad.ndjson"
    bad.write_text(
        json.dumps({"format": "some-other-format-v3"}) + "\n"
        + json.dumps({"type": "game_header", "game": 0, "headers": {}}) + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="chess4d-ndjson-v1"):
        read_ndjson_game(bad)


def test_read_ndjson_game_rejects_truncated_file(tmp_path: Path) -> None:
    """n_plies in the game header must match the record count."""
    result = generate_corpus(
        n_games=1, max_plies=6, seed=0, output_dir=tmp_path, encode=False
    )
    (s,) = result.games
    # Drop the last record — ``n_plies`` in the header still claims the
    # old count, so the reader should catch the mismatch.
    lines = s.ndjson_path.read_text(encoding="utf-8").splitlines()
    truncated = tmp_path / "short.ndjson"
    truncated.write_text("\n".join(lines[:-1]) + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match="expected"):
        read_ndjson_game(truncated)


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


# --- Two-pass (NDJSON-bridged) encoding ------------------------------------


def test_encode_ndjson_to_spectralz_full_game(tmp_path: Path) -> None:
    """Direct NDJSON → spectralz adapter, no tail. N+1 frames out."""
    gen = generate_corpus(
        n_games=1, max_plies=10, seed=0, output_dir=tmp_path, encode=False
    )
    (s,) = gen.games
    sz_path = tmp_path / "out.spectralz"
    pivot, encoded_plies, nbytes = encode_ndjson_to_spectralz(
        s.ndjson_path, sz_path
    )
    assert pivot == 0
    assert encoded_plies == s.plies
    assert nbytes > 0
    _, frames = read_spectralz_v4(sz_path)
    assert len(frames) == s.plies + 1
    assert [f.ply for f in frames] == list(range(s.plies + 1))


def test_encode_ndjson_to_spectralz_last_n(tmp_path: Path) -> None:
    """``last_n`` tail slice: 6 frames with absolute plies."""
    gen = generate_corpus(
        n_games=1, max_plies=20, seed=0, output_dir=tmp_path, encode=False
    )
    (s,) = gen.games
    sz_path = tmp_path / "tail.spectralz"
    pivot, encoded_plies, nbytes = encode_ndjson_to_spectralz(
        s.ndjson_path, sz_path, last_n=5
    )
    assert pivot == s.plies - 5
    assert encoded_plies == 5
    _, frames = read_spectralz_v4(sz_path)
    assert len(frames) == 6
    assert [f.ply for f in frames] == list(range(pivot, pivot + 6))


def test_two_pass_equivalence_byte_identical(tmp_path: Path) -> None:
    """Inline encoding == generate-then-retro-encode, byte-for-byte.

    Anchors the two-pass refactor: driving the encoder off the NDJSON
    produces the same spectralz bytes as driving it off the in-memory
    move list, because both paths resolve to the same
    ``write_spectralz(tail_start, tail_moves, base_ply=...)`` call.
    """
    # Path A — inline encode during playout.
    inline = generate_corpus(
        n_games=2,
        max_plies=15,
        seed=11,
        output_dir=tmp_path / "inline",
        encode_last=5,
        run_id="fixed",
    )
    # Path B — playout first, encode afterwards.
    bare = generate_corpus(
        n_games=2,
        max_plies=15,
        seed=11,
        output_dir=tmp_path / "bare",
        encode=False,
        run_id="fixed",
    )
    retro = encode_existing_run(bare.run_dir, last_n=5)
    assert len(inline.games) == len(retro.games) == 2
    for a, b in zip(inline.games, retro.games):
        assert a.encoding_path is not None
        assert b.encoding_path is not None
        assert a.encoding_path.read_bytes() == b.encoding_path.read_bytes()
        assert a.encoded_plies == b.encoded_plies
        assert a.pivot_ply == b.pivot_ply


def test_encode_existing_run_updates_manifest(tmp_path: Path) -> None:
    """Retro-encoding rewrites manifest fields to reflect the new pass."""
    bare = generate_corpus(
        n_games=2,
        max_plies=10,
        seed=3,
        output_dir=tmp_path,
        encode=False,
    )
    manifest_before = _read_manifest(bare.run_dir)
    assert manifest_before["fetch_params"]["encode"] is False
    assert manifest_before["aggregates"]["n_encoded_games"] == 0
    for row in manifest_before["games"]:
        assert row["spectralz"] is None
        assert row["spectralz_bytes"] is None

    encode_existing_run(bare.run_dir, last_n=3)

    manifest_after = _read_manifest(bare.run_dir)
    assert manifest_after["fetch_params"]["encode"] is True
    assert manifest_after["fetch_params"]["encode_last"] == 3
    assert manifest_after["aggregates"]["n_encoded_games"] == 2
    for row in manifest_after["games"]:
        assert row["spectralz"] == f"spectralz/{row['stem']}.spectralz"
        assert row["spectralz_bytes"] > 0
        assert row["encoded_plies"] == 3
        # Ply numbering stays absolute.
        assert row["pivot_ply"] == row["plies"] - 3


def test_encode_existing_run_missing_manifest(tmp_path: Path) -> None:
    """Retro-encoding a directory without a manifest raises."""
    empty = tmp_path / "empty_run"
    empty.mkdir()
    with pytest.raises(FileNotFoundError, match="manifest.json"):
        encode_existing_run(empty, last_n=5)


def test_encode_main_cli(tmp_path: Path) -> None:
    """``chess4d-corpus-encode`` CLI runs over a prior --no-encode run."""
    bare = generate_corpus(
        n_games=1,
        max_plies=10,
        seed=0,
        output_dir=tmp_path,
        encode=False,
    )
    rc = encode_main([str(bare.run_dir), "--last-n", "4"])
    assert rc == 0
    sz = bare.run_dir / "spectralz" / "game_001.spectralz"
    assert sz.exists()
    _, frames = read_spectralz_v4(sz)
    assert len(frames) == 5  # last-n=4 → 4 moves + 1 sentinel
    # Manifest now reports the encoded pass.
    manifest = _read_manifest(bare.run_dir)
    assert manifest["fetch_params"]["encode"] is True
    assert manifest["fetch_params"]["encode_last"] == 4
