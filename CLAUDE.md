# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository status

This repo is **pre-implementation**. The working tree currently contains only:

- `LICENSE` — Unlicense
- `hoodoos/oana-chiru-2026.pdf` and `hoodoos/oana-chiru-2026.xml` — the source paper this project implements (Oana & Chiru, *A Mathematical Framework for Four-Dimensional Chess*, MDPI AppliedMath 6(3):48, 2026, DOI 10.3390/appliedmath6030048)

There is no Python package, no dependency manifest, no tests, no CI, and no README. Build/lint/test commands do not yet exist — do not invent them. When starting the implementation, establish the packaging choice (e.g. `pyproject.toml` + `pytest`) and update this file.

The repo name (`python-chess4d-oana-chiru`) indicates the goal: a Python reimplementation of the 4D chess engine the paper describes. The paper's own reference implementation is JavaScript (engine + Three.js UI) — treat it as the prior art to port, not as code to import.

## The spec is the paper

`hoodoos/oana-chiru-2026.xml` is JATS XML and is greppable — prefer it over the PDF for lookup. Section numbers below refer to that document.

When asked to implement a mechanic, locate its definition in the paper first (§2–3 for math, §4 for engine/UI, §4.2 for special rules, §4.6 for complexity). The paper contains exact formulas, pseudocode listings, and boundary-case analyses that must be preserved verbatim in the port.

## Architectural invariants (from the paper)

These are load-bearing constraints the Python implementation must match; they are not design choices to revisit without reading the source paper.

- **Board domain.** `B = {1,…,8}^4 ⊂ Z^4` — a hypercubic lattice of 4096 squares. Positions are 4-tuples `(x, y, z, w)`. Adjacency uses the Chebyshev metric.
- **Piece-list move generation.** The initial position has ~896 pieces; a dense 4096-cell array is wasteful. Store occupied coordinates grouped by color/type and iterate those. This is analogous to piece-list/bitboard engines but extended to Z^4.
- **Displacements live in Z^4.** Each piece type owns a displacement set. Sliding pieces (rook, bishop, queen) ray-march along a chosen direction until leaving the board or hitting a blocker. Leapers (knight, king) enumerate a fixed displacement set. The queen is deliberately restricted to 1- and 2-axis moves; do not add 3- or 4-axis diagonals (doing so collapses bishop/rook/queen into one class — see Definition 7 in the paper).
- **Pawn orientation.** Each pawn is fixed at initialization as either **Y-oriented** or **W-oriented** and never changes. Promotion occurs at the terminal boundary of the pawn's forward axis (`y ∈ {1, 8}` or `w ∈ {1, 8}` depending on color and orientation). Y↔W symmetry means the pawn rule logic should be written once and parameterized by axis.
- **Parity invariant.** `π(x, y, z, w) = (x + y + z + w) mod 2` is preserved by every bishop move, so the bishop graph has exactly two connected components. Any test or evaluator touching bishops must respect this.
- **Multi-king legality.** The initial density produces multiple kings per side. A move is legal iff, after the move, **no king of the moving side is attacked** (§3, Definition 3). Check, checkmate, and stalemate generalize by quantifying over the full set of the side's kings, not a single king. This is not optional — the whole legality pipeline is built around it.
- **Castling** is restricted to the X-axis within a single `(z, w)`-slice. The king's path must not be attacked from *any* `(z', w')`-slice (attacks are global in 4D), even though the move itself is local.
- **En passant** is defined independently for Y-oriented and W-oriented pawns, consistent with the two allowed forward axes.
- **Draw detection.** Maintain a hash of the full 4D state for threefold repetition and a half-move clock for the 50-move rule; both extend directly from FIDE.
- **Pseudo-mobility bounds.** `M_max = 80` (king), `48` (knight), `28` (rook); bishop and queen are position-dependent due to ray truncation at boundaries. Attack-map construction is `O(P · M_max)` and is negligible compared to search-tree growth.

## Visualization (paper §4.3)

The paper's UI arranges 64 `(z, w)`-slices as an 8×8 grid of 8×8 boards ("checkerboard of chessboards"), all rendered simultaneously with transparency for depth. Camera navigation is quaternion-based in **SO(3) only** — the UI does *not* implement true 4D rotations (SO(4)). When a piece is selected, legal targets are highlighted on whichever slice they occupy, even if that slice differs from the selection's slice. The reference implementation uses Three.js; a Python port would typically substitute a web frontend, PyOpenGL/moderngl, or a game framework — choose after the engine core is working.

## Indexing gotcha

The paper uses 1-based theoretical coordinates `{1,…,8}^4`, but the reference UI is 0-based: the central `2×2` block of mixed-color slices is at theoretical `(z, w) ∈ {4, 5}×{4, 5}` and UI `(z, w) ∈ {3, 4}×{3, 4}`. Pick one convention internally and document it; convert only at the UI boundary.

## `hoodoos/` directory

The unusual name is just where the source paper lives. Treat it as read-only reference. Do not rename without checking with the user.
