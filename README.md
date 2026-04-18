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

## Development

```bash
pip install -e .[dev]
pytest -v
mypy --strict src/chess4d
ruff check src tests
```

## License

Unlicense (public domain). See `LICENSE`.
