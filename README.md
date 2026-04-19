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

Pre-alpha. Currently implemented: core types (`Square4D`, `Move4D`,
`Piece`, `Color`, `PieceType`, `PawnAxis`). Rook move generation and
invariant tests are next. Other pieces and the legality pipeline are stubs.

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

Generate a reproducible random-playout corpus:

```bash
chess4d-corpus-gen --n-games 10 --seed 42 --output ./corpus
```

The 11 channels cover the six piece types (with pawns split by forward
axis per Oana & Chiru Def. 11) plus board-parity and side-to-move
signals. See the `chess-spectral` notebooks in the mlehaptics repo for
channel semantics and reconstruction examples.

## Development

```bash
pip install -e .[dev]
pytest -v
mypy --strict src/chess4d
ruff check src tests
```

## License

Unlicense (public domain). See `LICENSE`.
