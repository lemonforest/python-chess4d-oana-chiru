# python-chess4d-oana-chiru

Python reference implementation of:

> Oana & Chiru, *A Mathematical Framework for Four-Dimensional Chess*,
> MDPI AppliedMath **6**(3):48, 2026. DOI [10.3390/appliedmath6030048](https://doi.org/10.3390/appliedmath6030048).

The source paper lives in `hoodoos/` (treat as read-only reference).

## Coordinate convention

Internally 0-based: `B = {0,…,7}^4 ⊂ Z^4` (4096 cells). The paper's 1-based
`{1,…,8}^4` notation is preserved in docstrings and converted only at the
UI boundary. See `CLAUDE.md` for the indexing gotcha (the reference UI is
also 0-based; the central mixed-color slice block is at theoretical
`(z, w) ∈ {4, 5}×{4, 5}` / UI `(z, w) ∈ {3, 4}×{3, 4}`).

## Status

0.2.0 — core engine, legality, and corpus tooling are in. Implemented:
all six piece types with paper-faithful move generation (rook / bishop /
knight / queen / king / pawn), multi-king legality per §3.4 Def 3
(a move is legal iff *no* king of the mover is attacked afterwards),
X-axis castling with global attack safety, Y- and W-axis en passant,
pawn promotion on the terminal rank of each forward axis, draw detection
(50-move rule + threefold repetition via 4D state hash), `.c4d` move
notation with round-trip I/O, chess-spectral integration (optional),
and a random-playout corpus generator writing the
`chess-maths-the-movie` nested layout.

Not yet implemented: search / evaluation, a UI, Oana-Chiru 4D-aware
opening books. See `CLAUDE.md` for architectural invariants.

## Spectral encoding (optional)

chess4d integrates with the `chess-spectral` framework (developed in the
sibling `mlehaptics` repo) for physics-grounded analysis of 4D positions.
The encoder maps a `GameState` to an 11-channel, 45 056-dimensional
float32 spectral vector and writes streams of frames as `spectralz` v4
files. Install with the `spectral` extra (pulls `chess-spectral` directly
from GitHub, plus numpy and scipy):

```bash
pip install -e .[spectral]
```

Encode a single position:

```python
from chess4d import initial_position
from chess4d.spectral import encode_position

gs = initial_position()
vec = encode_position(gs)  # (45056,) float32
```

Encode a game and write it to a `spectralz` v4 file:

```python
from chess4d.spectral import write_spectralz

write_spectralz("game.spectralz", start_state, move_list)
```

The 11 channels cover the six piece types (with pawns split by forward
axis per Oana & Chiru Def. 11) plus board-parity and side-to-move
signals. See the `chess-spectral` notebooks in the mlehaptics repo for
channel semantics and reconstruction examples.

## Corpus generation

`chess4d-corpus-gen` writes a reproducible random-playout corpus in the
`chess-maths-the-movie` nested layout:

```
./corpus/<run_id>/
  manifest.json                    # run metadata + per-game rows
  c4d/game_NNN.c4d                 # compact 4D move notation
  ndjson/game_NNN.ndjson           # per-ply pos4 snapshots + moves
  spectralz/game_NNN.spectralz     # 45 056-dim per-ply encoding (optional)
```

`<run_id>` is auto-minted as `corpus_YYYYMMDD_HHMMSS_seedN` (or
`..._unseeded`) and can be overridden with `--run-id`. Generation is
two-pass: the playout pass writes c4d + NDJSON unconditionally, then an
optional encoding pass reads the NDJSON and produces spectralz frames
with absolute ply numbers.

```bash
# default: full-game spectralz for every ply
chess4d-corpus-gen --n-games 10 --seed 42 --output ./corpus

# only encode the final 30 plies per game (c4d + NDJSON still full)
chess4d-corpus-gen --n-games 1 --max-plies 500 --encode-last 30

# playout only — c4d + NDJSON, no spectralz, no [spectral] extra needed
chess4d-corpus-gen --n-games 10 --seed 42 --no-encode

# reproducible named run
chess4d-corpus-gen --n-games 10 --seed 42 --run-id fixed-corpus-v1
```

### Retro-encoding an existing corpus

Because encoding reads from the NDJSON sidecar, you can turn a
`--no-encode` corpus into a spectralz corpus at any point without
replaying the games:

```bash
# encode every ply of every game in an existing run
chess4d-corpus-encode ./corpus/corpus_20260419_180342_seed42

# tail-only: encode just the final 30 plies of each game
chess4d-corpus-encode ./corpus/corpus_20260419_180342_seed42 --last-n 30
```

The standalone CLI is driven entirely by NDJSON and updates
`manifest.json` in place. For a given `(seed, last_n)`, the
retro-encoded spectralz bytes are identical to those produced by
`chess4d-corpus-gen --encode-last N` on the same inputs.

The NDJSON schema is `chess4d-ndjson-v1`: line 1 is the format header,
line 2 is a `game_header` record with termination / ply count / seed,
and subsequent lines carry per-ply records with the applied move,
`side_to_move`, and a full `pos4` dict (2-char pawn values
`Pw`/`Py`/`pw`/`py`, 1-char non-pawns, keyed by linear square index
`(x<<9) | (y<<6) | (z<<3) | w`).

## Development

```bash
pip install -e .[dev]
pytest -v
mypy --strict src/chess4d
ruff check src tests
```

## License

Unlicense (public domain). See `LICENSE`.
