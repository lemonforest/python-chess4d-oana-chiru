# Phase 2 — Bishop move generation

## Before starting: commit and sync Phase 1

Deliverable 2 (rook + primitives + push/pop) is complete and verified.
Before any Phase 2 work, commit the current tree and push:

```
git status                   # confirm clean working tree or expected changes only
git add -A
git commit -m "Phase 1 complete: rook move generation, Board4D push/pop, primitives

- Square4D.in_bounds / .parity / .chebyshev_distance
- Board4D with piece-list storage, place/remove/push/pop, undo stack
- Precomputed ROOK_DIRECTIONS / ROOK_RAYS / ROOK_NEIGHBORS geometry
- rook_moves generator respecting blockers and captures
- IllegalMoveError domain exception
- Tests: 60/60 passing (primitives, adjacency, moves, push/pop)
- Theorem 1, Corollary 1, Theorem 2, Proposition 2(i) all covered

Paper: Oana & Chiru 2026, §3.1, §3.2 Def 1, §3.5, §3.7 Lemma 2,
§3.8 Prop 2."
git push
```

Confirm the push succeeded before proceeding.

---

/plan

## Phase 2 goal

Add bishop move generation, matching the architectural pattern
established in Phase 1. Same shape: precomputed geometry module
contribution + pieces/bishop.py generator + test file(s) + push
support. No changes to rook, board state model, or legality pipeline.

## Sources of truth (same hierarchy as Phase 1)

1. Paper (`hoodoos/oana-chiru-2026.xml`):
   - §3.7, Definition 6 — bishop displacement set
   - §3.7, Lemma 2 — parity invariance
   - §3.7, Theorem 4 — exactly two connected components
   - §3.7, Lemma 5 — six coordinate planes
   - §3.8, Proposition 2(ii) — bishop preserves parity
   - §3.8 closed-form mobility formula — per-plane distance-to-boundary sum
2. JS reference (https://github.com/oanaunc/4d_chess) if the paper is
   ambiguous on an edge case. Cite the file/line in a comment if used.
3. Do not invent behavior. Flag ambiguities as TODO with a documented
   assumption.

## Architectural invariants (locked from Phase 1)

- Bishop displacement set per Definition 6: exactly two nonzero
  components, equal absolute value, other two components zero. Six
  coordinate planes: XY, XZ, XW, YZ, YW, ZW.
- Parity ``π(x,y,z,w) = (x+y+z+w) mod 2`` is preserved by every bishop
  move. The bishop graph has exactly two connected components.
- Sliding semantics match the rook: ray-march from origin along a
  plane's diagonal directions, stop at board edge or first blocker,
  yield capture on enemy blocker.
- Four diagonal directions per plane: (+,+), (+,−), (−,+), (−,−).
  Six planes × four directions = 24 rays per square.
- Like the rook, bishop pseudo-legal moves do not enforce king safety.
  That's still the legality pipeline's job.

## Deliverables

### 1. Geometry additions to `src/chess4d/geometry.py`

Add alongside the existing rook geometry:

- `BISHOP_PLANES: tuple[tuple[int, int], ...]` — the six axis-pair
  planes as coordinate-index tuples. Use `(0, 1)` for XY, `(0, 2)`
  for XZ, etc., so that code generating displacements can index into
  `Square4D` directly.
- `BISHOP_DIRECTIONS: tuple[Displacement, ...]` — 24 unit diagonal
  displacements (6 planes × 4 sign combinations).
- `BISHOP_RAYS: Mapping[Square4D, tuple[tuple[Square4D, ...], ...]]`
  — same shape as `ROOK_RAYS`: per-square 24-tuple of ordered rays,
  nearest-to-farthest, excluding the origin.
- `BISHOP_NEIGHBORS: Mapping[Square4D, frozenset[Square4D]]` — flat
  empty-board reach (union of the 24 rays).

Direction ordering in `BISHOP_DIRECTIONS` is load-bearing — tests will
depend on it. Pick a deterministic order (plane order × sign order)
and document it in the module docstring.

### 2. `src/chess4d/pieces/bishop.py`

Mirror `rook.py` exactly:

- `bishop_moves(origin: Square4D, color: Color, board: Board4D) -> Iterator[Move4D]`
- Iterate `BISHOP_RAYS[origin]`, walk each ray, yield empty squares,
  yield captures and stop, stop silently on friendly blockers.
- Docstring cites §3.7 Def 6 and Lemma 2.

### 3. Update `src/chess4d/pieces/__init__.py`

Export `bishop_moves` alongside `rook_moves`.

### 4. Update `src/chess4d/__init__.py`

Export `bishop_moves` from the public API.

### 5. Extend `Board4D.push`

Accept bishop moves. The cleanest change:

- Remove the "only rook moves supported" hard rejection.
- Dispatch on `piece.piece_type`: for rook use `ROOK_NEIGHBORS` +
  ray-walk; for bishop use `BISHOP_NEIGHBORS` + diagonal ray-walk.
- Factor the dispatch so adding knight/king/queen/pawn later is a
  one-line addition per piece type, not another elif-rewrite.
- Other piece types still raise `IllegalMoveError` with a
  "not yet supported in this phase" message.

Consider pulling the ray-walk validation into a helper that takes the
origin, target, and the relevant `_RAYS` mapping — `_walk_ray_or_raise`
currently hard-codes axis-unit detection and won't generalize to
diagonals cleanly. Refactor to a shape that looks up the ray directly:
find the ray in `RAYS[from_sq]` that contains `to_sq`, then check the
intervening squares from that ray.

### 6. Tests

Create `tests/test_bishop_adjacency.py` and `tests/test_bishop_moves.py`
mirroring the rook test structure. Required invariant coverage:

**`test_bishop_adjacency.py`:**
- Closed-form mobility per §3.8: sum over 6 planes of
  `d_++ + d_+- + d_-+ + d_--` (min-to-boundary along each diagonal
  direction in the plane). Verify on all 4096 squares.
- Interior mobility (§3.7 Lemma 3, squares in `{2,3,4,5}^4` 0-based)
  equals the maximum — each diagonal of length up to 2 is available
  in both directions on every plane. Compute the exact number and
  assert it.
- Corner mobility: `(0,0,0,0)` has only one diagonal direction per
  plane (`++`), so total mobility is `6 × 7 = 42`. Verify.
- Parity invariance (§3.7 Lemma 2): every square in
  `BISHOP_NEIGHBORS[sq]` has the same parity as `sq`. Verify on all
  4096 squares.
- Parity bipartition (§3.7 Theorem 4): BFS from `(0,0,0,0)` reaches
  exactly `8^4 / 2 = 2048` squares, and all of them have parity 0.
  BFS from `(1,0,0,0)` reaches 2048 squares, all parity 1. The two
  sets are disjoint and union to `B`.
- Six-plane structure (§3.7 Lemma 5): confirm `len(BISHOP_PLANES) == 6`
  and that each plane uses a distinct pair of axis indices.
- Direction sanity: every entry in `BISHOP_DIRECTIONS` has exactly
  two nonzero components, both `±1`, and the zero components match
  one of the six planes.

**`test_bishop_moves.py`:**
- `bishop_moves` on empty board matches `BISHOP_NEIGHBORS` cardinality
  for every square (sample, not exhaustive — ~50 squares is fine).
- Moves are axis-diagonal: every generated move changes exactly two
  coordinates by equal absolute value.
- Parity flip (§3.8 Prop 2(ii)): every bishop move preserves parity.
  Property-test with Hypothesis.
- Blocker behavior: friendly piece stops the ray without capture,
  enemy piece is captured and the ray stops. Two explicit cases per
  direction class (same plane but different signs) to catch off-by-one
  bugs in ray direction lookup.
- Corner (0,0,0,0): exactly 42 moves, all with `to_sq.x >= 0 && ...`.
- Interior mobility matches the closed-form.

**Push/pop coverage:**
- Add bishop push/pop tests to `test_rook_push_pop.py` (or rename the
  file to `test_push_pop.py` since it now covers multiple pieces).
- Mixed-sequence Hypothesis property: push a random mix of legal rook
  and bishop moves, pop them all, assert bit-identical state. Extend
  the existing `_random_legal_rook_sequence` helper to cover bishops.

### 7. Out of scope

- Knight, king, queen, pawn move generation
- Castling, promotion, en passant
- Multi-king check detection, legality filtering
- Draw rules
- Any encoder integration
- Any UI/rendering work

## Request before writing code

Before implementing, show me:

1. The `BISHOP_DIRECTIONS` ordering you've chosen and the rationale
   (tests will pin this, so commit to it once).
2. The refactored `Board4D._walk_ray_or_raise` signature — how the
   dispatch between rook (axis-aligned) and bishop (planar-diagonal)
   ray validation works.
3. The `test_bishop_adjacency.py` skeleton (test function names +
   one-line purpose each) so I can confirm the invariants are covered
   before you implement the generator.

Do not start coding `bishop_moves` itself until I sign off on those
three items.

## After Phase 2

Same handoff shape as Phase 1:
- All tests passing (new + existing — Phase 1 rook tests must not
  regress)
- `mypy --strict` clean on all of `src/chess4d`
- `ruff check src tests` clean
- Smoke test: play a short game mixing rook and bishop moves,
  push/pop-symmetric, report final state matches initial