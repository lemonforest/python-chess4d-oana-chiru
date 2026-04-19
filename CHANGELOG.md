# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.2.0] — 2026-04-19

Corpus restructure: nested `<run_id>/` layout, NDJSON per-ply snapshots,
and full `manifest.json` schema — drops into the `chess-maths-the-movie`
toolchain alongside the 2D chess spectral viewer.

### Added

- Nested corpus layout: `<output>/<run_id>/{manifest.json, c4d/, ndjson/, spectralz/}`.
- NDJSON schema `chess4d-ndjson-v1` — format header + game header + per-ply
  records carrying a `pos4` dict (2-char pawn values `Pw`/`Py`/`pw`/`py`,
  1-char non-pawns), keyed by the linear square index
  `(x<<9) | (y<<6) | (z<<3) | w`.
- `manifest.json` top-level schema: `generated_utc`, `run_id`, `source`,
  `fetch_params`, `tool_versions`, `aggregates`, `games[]`.
- `CorpusResult` dataclass returned from `generate_corpus()`; `GameSummary`
  gains `stem`, `c4d_path`, `ndjson_path`, `encoding_path`, `plies`,
  `encoded_plies`, `pivot_ply`, `termination`, and matching byte-count fields.
- Auto-generated `run_id` of the form `corpus_YYYYMMDD_HHMMSS_seedN` (or
  `..._unseeded`); override via the `--run-id` CLI flag or `run_id=` kwarg.
- `write_spectralz(..., base_ply=N)` kwarg: frame `ply` numbers are written
  with an absolute offset, so tail-encoded spectralz files join cleanly
  against the full-game NDJSON by absolute ply.
- `--no-encode` CLI flag runs the full corpus pipeline on a bare install
  without the `[spectral]` extra (`chess_spectral` import is lazy).
- `NDJSON_FORMAT_ID` and `_auto_run_id` exposed as module-level names for
  reuse in downstream tools.

### Changed

- `generate_corpus()` now returns `CorpusResult` (previously
  `list[GameSummary]`). Callers iterating the return value should switch
  to `result.games`.
- Flat `game_NNN.{json,spectralz}` output layout from the in-progress
  branch has been replaced by the nested `<run_id>/` layout before
  landing — no released version exposed the flat form.

### Fixed

- Manifest byte-count fields now match on-disk file sizes on Windows,
  where `Path.write_text` translates `\n` to `\r\n`. Writers now report
  `Path.stat().st_size` instead of `len(text.encode("utf-8"))`.
- `manifest.tool_versions.chess4d` is now populated. The distribution
  name is `python-chess4d-oana-chiru`, not `chess4d`, so the previous
  `importlib.metadata.version("chess4d")` call raised
  `PackageNotFoundError` and silently dropped the field.

## [0.1.1] — prior release

- Startpos pawn-axis fix: pawns on the `y ∈ {1, 6}` ranks now alternate
  Y-/W-orientation with `x` per paper §3.3.

## [0.1.0] — prior release

- Initial tagged release: engine core, legality, notation, spectral
  encoder integration (Phase 8), CLI skeleton.
