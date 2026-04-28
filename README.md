# python-chess4d-oana-chiru

[![PyPI](https://img.shields.io/pypi/v/python-chess4d-oana-chiru.svg)](https://pypi.org/project/python-chess4d-oana-chiru/)
[![Python versions](https://img.shields.io/pypi/pyversions/python-chess4d-oana-chiru.svg)](https://pypi.org/project/python-chess4d-oana-chiru/)
[![License: Unlicense](https://img.shields.io/badge/license-Unlicense-blue.svg)](LICENSE)

Python reference implementation of:

> Oana & Chiru, *A Mathematical Framework for Four-Dimensional Chess*,
> MDPI AppliedMath **6**(3):48, 2026. DOI [10.3390/appliedmath6030048](https://doi.org/10.3390/appliedmath6030048).

The source paper lives in `hoodoos/` (treat as read-only reference).

## Install

From [PyPI](https://pypi.org/project/python-chess4d-oana-chiru/) (recommended):

```bash
# Core engine + corpus CLI (.c4d + NDJSON outputs; no encoder).
pip install python-chess4d-oana-chiru

# With the chess-spectral encoder pulled in (45 056-dim float32
# vectors + spectralz v4 frame format; brings numpy/scipy along).
pip install "python-chess4d-oana-chiru[spectral]"
```

From source (for local development):

```bash
git clone https://github.com/lemonforest/python-chess4d-oana-chiru
cd python-chess4d-oana-chiru
pip install -e ".[dev,spectral]"
```

Type hints ship with the package (`py.typed` marker per PEP 561) and are
checked with `mypy --strict` in CI.

## Coordinate convention

Internally 0-based: `B = {0,…,7}^4 ⊂ Z^4` (4096 cells). The paper's 1-based
`{1,…,8}^4` notation is preserved in docstrings and converted only at the
UI boundary. See `CLAUDE.md` for the indexing gotcha (the reference UI is
also 0-based; the central mixed-color slice block is at theoretical
`(z, w) ∈ {4, 5}×{4, 5}` / UI `(z, w) ∈ {3, 4}×{3, 4}`).

## Status

0.4.0 — core engine, legality, corpus tooling, and native (C)
spectralz encoder integration are all in. Implemented:
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

chess4d integrates with the
[`chess-spectral`](https://pypi.org/project/chess-spectral/) framework
(developed in the sibling `mlehaptics` repo, published to PyPI) for
physics-grounded analysis of 4D positions. The encoder maps a
`GameState` to an 11-channel, 45 056-dimensional float32 spectral
vector and writes streams of frames as `spectralz` v4 files. Install
the `spectral` extra to pull in `chess-spectral` (brings numpy + scipy
along transitively):

```bash
pip install "python-chess4d-oana-chiru[spectral]"
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

### Encoder selection

`--encoder` picks the spectralz encoder backend:

| Mode | Behavior |
|---|---|
| `auto` (default) | Use the bundled C `spectral_4d` binary if `chess-spectral` ships one for your platform; otherwise fall back to the Python `encode_4d` adapter. |
| `native` | Require the C binary; raise if it's not bundled in the installed `chess-spectral` (e.g. `py3-none-any` fallback wheel). |
| `python` | Force the pure-Python encoder. Used to keep deterministic-bit-pattern reproducibility against legacy reference output. |

The two backends agree to within float32 precision. The Python path
emits ~`2^-55` accumulation noise in the A_1 channel that the C path
zeros out — max abs diff `≈ 2.78e-17`, ten orders of magnitude below
float32 epsilon. Channels 1–10 are bit-identical between the two.

```bash
# auto (uses the C binary on supported platforms — recommended)
chess4d-corpus-gen --n-games 10 --seed 42

# explicit native (raise if no binary)
chess4d-corpus-gen --n-games 10 --seed 42 --encoder native

# force Python (for byte-identical reproducibility against pre-0.4.0 reference)
chess4d-corpus-gen --n-games 10 --seed 42 --encoder python
```

### Move-operator selection

`--move-operator` controls how legal moves are generated during
random playout. `spatial` (default) uses chess4d's existing
geometric engine. `phase` is reserved for a future PR that will
route through `chess_spectral.phase_operators_4d`'s phase-space
move kernels — selecting it today raises `NotImplementedError`.

### Seeding semantics

`--seed N` seeds a **single `random.Random(N)`** instance that is
**shared across every game in the run**. The only thing that RNG drives
is the move choice (`rng.choice(legal_moves)`); the starting position
is always the canonical Oana-Chiru §3.3 layout and is *not* seeded.

Because the RNG is deterministic, a corpus produced with a given
`(max_plies, seed)` is actually an **infinite deterministic sequence**
of games, and `--n-games N` just asks for the first *N* of them. That
gives you this prefix property:

| Run A | Run B | Overlap |
|---|---|---|
| `--n-games 10 --seed 42` | `--n-games 5 --seed 42` | Games 1..5 are byte-identical |
| `--n-games 3 --seed 42` | `--n-games 100 --seed 42` | Games 1..3 are byte-identical |
| `--n-games 10 --seed 42` | `--n-games 10 --seed 43` | Share nothing; different stream |

So growing or shrinking `--n-games` *extends* the corpus forward or
*truncates* it — it never changes earlier games. The same is true of
all three outputs (`c4d`, `ndjson`, `spectralz`).

What the shared-RNG design **doesn't** give you is the ability to
reproduce game *i* in isolation: to get game 5's exact moves you have
to run games 1..4 first, because game 5's starting RNG state is "seed
42, advanced past the draws games 1..4 consumed." Per-game seed
derivation (so each game's RNG is derived independently from the base
seed + game index) is deliberately deferred to a future release — the
corpus-level seed is enough for the full-corpus replay use case, which
is what the `fetch_params.seed` field in `manifest.json` records.

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
