# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.3.1] — 2026-04-19

Packaging-only release: the project is now installable from PyPI.

### Changed

- `[spectral]` extra now depends on `chess-spectral>=1.1.1` from PyPI
  instead of the PEP 508 direct reference
  `chess-spectral @ git+https://github.com/.../mlehaptics.git@chess-spectral-v1.1.1#subdirectory=...`.
  PyPI rejects uploads whose metadata contains direct references, so
  the prior form blocked distribution. Same content pinned at the
  same lower bound; the spectralz-v4 bit-level encoding contract is
  preserved. No user-visible API change.
- `[tool.hatch.metadata] allow-direct-references` removed as a
  consequence — no longer needed without the git+https URL.

### Added

- `src/chess4d/py.typed` marker — downstream users' mypy now sees
  the engine's type hints without extra configuration (PEP 561).
- PyPI metadata polish in `pyproject.toml`: `keywords`, `classifiers`
  (SemVer-stable Trove set: Science/Research, Board Games, Typed,
  Python 3.11/3.12), and `project.urls` (Homepage, Issues, Changelog,
  Paper).
- Explicit `[tool.hatch.build.targets.sdist] include = [...]`
  allowlist so the uploaded tarball only carries source + user-facing
  docs (no `.claude/`, `smoke/`, `hoodoos/`, `benches/`, `CLAUDE.md`).
- `.github/workflows/publish-to-pypi.yml`: OIDC trusted-publishing
  workflow that builds sdist + wheel, runs `twine check --strict`,
  and publishes to PyPI via the `pypi` environment. Triggered by
  `push: tags: ["v*"]`, by `workflow_dispatch`, or by autotag.yml's
  cascade dispatch (see below).
- `.github/workflows/autotag.yml`: after a successful tag push, now
  dispatches `publish-to-pypi.yml` via `gh workflow run`. This is
  necessary because `GITHUB_TOKEN`-initiated tag pushes do not
  cascade a `push: tags` trigger on other workflows —
  `workflow_dispatch` is the documented exemption.

## [0.3.0] — 2026-04-19

Two-pass corpus flow with NDJSON as the bridge between the playout
and encoding passes, plus a standalone `chess4d-corpus-encode` CLI
for retro-encoding any existing corpus. No breaking API changes;
byte-identical spectralz output is preserved across both the inline
and retro-encoded paths.

### Added

- `chess4d.corpus.read_ndjson_game(path) -> (GameState, list[Move4D], dict)` —
  parses chess4d-ndjson-v1 files back into the `(start, moves)` pair the
  encoder needs. Validates the format header, ply numbering, and that
  ply-0 `pos4` matches `initial_position()`.
- `chess4d.corpus.encode_ndjson_to_spectralz(ndjson, sz, *, last_n=None)` —
  NDJSON → spectralz adapter. `last_n` honors the same
  absolute-ply semantics as `--encode-last`.
- `chess4d.corpus.encode_existing_run(run_dir, *, last_n=None)` —
  retro-encodes a `--no-encode` corpus: iterates the NDJSON sidecars,
  writes `spectralz/` files, and rewrites `manifest.json` in place.
- `chess4d-corpus-encode <run_dir> [--last-n N]` — standalone CLI entry
  point for the retro-encode flow; registered under `[project.scripts]`.

### Changed

- `generate_corpus()` internals are now two-pass: the playout pass
  writes `c4d/` and `ndjson/` unconditionally, then (if encoding is
  requested) a second pass drives the spectralz writer off the NDJSON
  sidecar rather than the in-memory move list. Public API, CLI
  flags, output layout, and spectralz byte-exactness are unchanged —
  `test_two_pass_equivalence_byte_identical` anchors this.
- README status section: the stale "Pre-alpha… rook moves are next"
  paragraph now reflects the shipped engine (all pieces, legality,
  notation round-trip, corpus generator). Added a "Corpus generation"
  section documenting the nested layout, the four CLI modes, the
  retro-encode flow, and the `chess4d-ndjson-v1` schema.

### Removed

- Dead `_state_after` helper in `chess4d.corpus` — superseded by the
  replay loop inside `encode_ndjson_to_spectralz`.

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
