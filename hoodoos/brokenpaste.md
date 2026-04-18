# Phase 3 — Remaining piece-move generators (batched)

## Scope

Ship queen, knight, king, and pawn move generation in one session, with
a git commit after each piece. The dispatch table and ray-walk
infrastructure from Phase 2 generalize; this phase proves it by
adding pieces of progressively different shapes (slider-union, leaper,
trivial leaper, axis-dependent specialist).

## Before starting: commit Phase 2 and enter plan mode

```
git status
git add -A
git commit -m "Phase 2 complete: bishop move generation, dispatch-table architecture

- BISHOP_PLANES, BISHOP_DIRECTIONS, BISHOP_RAYS, BISHOP_NEIGHBORS
- bishop_moves generator (sliding, parity-preserving)
- _PIECE_GEOMETRY dispatch table in Board4D
- _walk_ray_or_raise refactored to ray-lookup (generalizes to any slider)
- Tests: 88/88 passing (60 Phase 1 + 28 Phase 2)
- §3.7 Def 6, Lemma 2, Lemma 3, Lemma 5, Theorem 4; §3.8 Prop 2(ii),
  closed-form mobility

Paper: Oana & Chiru 2026, §3.7-§3.8."
git push
```

Confirm the push succeeded before proceeding.

/plan

## Overall architecture constraints (do not revisit)

- The `_PIECE_GEOMETRY` dispatch table is the extension point. Every
  new piece registers `PieceType.X: (X_RAYS, X_NEIGHBORS)` and inherits
  push/pop automatically. **Never add an elif chain in `push()`.**
- For sliders, `X_RAYS[sq]` is a tuple of ordered rays (nearest-to-
  farthest). For leapers, `X_RAYS[sq]` is a tuple of single-element
  rays — one per neighbor — so ray-walk validation is a no-op (there
  are no intermediate squares). This keeps `_walk_ray_or_raise` uniform.
- `X_NEIGHBORS[sq]` is always the flat frozenset of reachable targets
  on an empty board.
- Every piece generator lives in `src/chess4d/pieces/X.py` and follows
  the rook/bishop shape: take `(origin, color, board)`, yield `Move4D`.
- Pseudo-legal only. King safety (§3.4 Def 3) stays unimplemented.

## Sub-phase 3A — Queen (§3.8 Definition 7)

**Expected effort: ~30 lines. Queen = rook ∪ bishop.**

### Geometry additions to `src/chess4d/geometry.py`

- `QUEEN_DIRECTIONS = ROOK_DIRECTIONS + BISHOP_DIRECTIONS` (32 entries)
- `QUEEN_RAYS: Mapping[Square4D, tuple[tuple[Square4D, ...], ...]]` —
  per-square concatenation of the rook and bishop rays.
  `QUEEN_RAYS[sq] = ROOK_RAYS[sq] + BISHOP_RAYS[sq]`.
- `QUEEN_NEIGHBORS[sq] = ROOK_NEIGHBORS[sq] | BISHOP_NEIGHBORS[sq]`

**Critical constraint from §3.8 Definition 7:** the queen is 1- and
2-axis only. **Do not** add 3- or 4-axis diagonal directions. A
docstring comment stating this and citing the paper is mandatory.

### `src/chess4d/pieces/queen.py`

Replace the stub. The generator body is literally the bishop generator
with `QUEEN_RAYS` instead of `BISHOP_RAYS`. Consider factoring a shared
`_slide_generator(rays_map, origin, color, board)` helper used by rook,
bishop, queen — but only if the factoring is cleaner than copy-paste.
Use judgment.

### Register in dispatch table

`_PIECE_GEOMETRY[PieceType.QUEEN] = (QUEEN_RAYS, QUEEN_NEIGHBORS)`.

### Tests: `tests/test_queen_adjacency.py` + `tests/test_queen_moves.py`

Invariants:
- Queen mobility = rook mobility + bishop mobility per square (exact
  additivity from Definition 7's union construction). Verify on all
  4096 squares.
- Corner (0,0,0,0): `28 + 42 = 70` empty-board moves. Explicit test.
- Center like (3,3,3,3): `28 + 6×4×3 = 28 + 72 = 100`. Verify against
  closed-form.
- Queen can reach every square reachable by rook or bishop from the
  origin. Verify `QUEEN_NEIGHBORS[sq] == ROOK_NEIGHBORS[sq] |
  BISHOP_NEIGHBORS[sq]` on all 4096 squares.
- Queen cannot reach 3-axis-different squares (Definition 7
  restriction). Verify: for every `sq`, no element of
  `QUEEN_NEIGHBORS[sq]` has Hamming distance 3 or 4 from `sq`.
- Parity: queen moves flip parity by `d mod 2` along rook-type rays
  (§3.8 Prop 2(i)) and preserve parity along bishop-type rays
  (§3.8 Prop 2(ii)). Property-test with Hypothesis.
- Mixed-plane queen move push/pop: sanity test.

Commit after 3A:
```
git add -A
git commit -m "Phase 3A: queen = rook ∪ bishop (§3.8 Def 7)

1- and 2-axis moves only; 3- and 4-axis diagonals explicitly excluded.

Geometry: QUEEN_DIRECTIONS, QUEEN_RAYS, QUEEN_NEIGHBORS (unions).
Generator: queen_moves via shared ray-walk.
Dispatch: registered in _PIECE_GEOMETRY.
Tests: mobility additivity, Hamming-distance bound, parity split."
git push
```

## Sub-phase 3B — Knight (§3.8 Definition 8, Theorem 3)

**Expected effort: moderate. First leaper.**

### Geometry additions to `src/chess4d/geometry.py`

- `KNIGHT_DISPLACEMENTS: tuple[Displacement, ...]` — all permutations
  of `(±2, ±1, 0, 0)`. By §3.8 this is 48 displacements on an interior
  square. Deterministic order: iterate axis pairs (2-axis outer,
  1-axis inner) and sign combinations inner. Document the order.
- `KNIGHT_RAYS: Mapping[Square4D, tuple[tuple[Square4D, ...], ...]]` —
  **for leapers, each "ray" is a single-element tuple `(target,)`**.
  This uniform shape lets `_walk_ray_or_raise` treat leapers as sliders
  with no intermediate squares to check.
- `KNIGHT_NEIGHBORS: Mapping[Square4D, frozenset[Square4D]]` — flat
  reach set. Boundary-clipped per §3.8 Theorem 3.

### `src/chess4d/pieces/knight.py`

Same shape as bishop, but since leaper rays have length 1, the "walk
until blocker" loop terminates immediately on the single target. The
existing generator logic works unchanged:

```python
for ray in KNIGHT_RAYS[origin]:
    for target in ray:  # single iteration for leapers
        occupant = board.occupant(target)
        if occupant is None:
            yield Move4D(from_sq=origin, to_sq=target)
            continue
        if occupant.color != color:
            yield Move4D(from_sq=origin, to_sq=target)
        break
```

If this reads awkwardly for a leaper, factor the slider and leaper
generators. Use judgment.

### Register in dispatch table

`_PIECE_GEOMETRY[PieceType.KNIGHT] = (KNIGHT_RAYS, KNIGHT_NEIGHBORS)`.

### Tests: `tests/test_knight_adjacency.py` + `tests/test_knight_moves.py`

Invariants from §3.8 Theorem 3:
- Interior (0-based `{2,3,4,5}^4`) mobility = 48. All 256 interior
  squares. Explicit.
- Closed-form degree formula from Theorem 3:
  `deg_N(p) = (Σ c_2(u_i))(Σ c_1(u_i)) - Σ c_2(u_i) c_1(u_i)`
  where `c_1(u) = [l(u) ≥ 1] + [r(u) ≥ 1]` and
  `c_2(u) = [l(u) ≥ 2] + [r(u) ≥ 2]`, with `l(u) = u`, `r(u) = 7-u`.
  Verify on all 4096 squares. (Note: paper's indexing is 1-based so
  `l(u) = u-1`; convert to 0-based.)
- Corner (0,0,0,0): low mobility — compute expected from the formula
  and assert exactly.
- Parity: knight moves always flip parity (§3.8 Prop 2(iii)).
  Property-test with Hypothesis.
- Edge-support orthogonality sanity: knight neighbors are disjoint
  from rook, bishop, king neighbors of the same square (no shared
  edges — from your own chess_spectral_4d notebook's Claim 1).
  Verify on a sample of ~20 squares.
- Knight moves through "blockers": knight is a leaper, so placing a
  piece on an intermediate square (e.g., `(1,0,0,0)` when knight moves
  from `(0,0,0,0)` to `(2,1,0,0)`) does NOT block the move. Explicit
  test.
- Knight captures: standard friendly-blocks / enemy-captures.

Commit after 3B:
```
git add -A
git commit -m "Phase 3B: knight leaper (§3.8 Def 8, Theorem 3)

First non-slider piece; leaper rays represented as length-1 tuples so
the shared ray-walk treats it uniformly.

Geometry: 48 (±2,±1,0,0) permutations, boundary-clipped KNIGHT_NEIGHBORS.
Generator: knight_moves (jumps over intermediate squares).
Dispatch: registered in _PIECE_GEOMETRY.
Tests: interior mobility 48, closed-form stratification, parity flip,
edge-support orthogonality, leaper-over-blocker."
git push
```

## Sub-phase 3C — King (§3.9 Definition 9)

**Expected effort: small. Chebyshev-1 leaper.**

### Geometry additions to `src/chess4d/geometry.py`

- `KING_DISPLACEMENTS: tuple[Displacement, ...]` — all 80 nonzero
  vectors in `{-1, 0, +1}^4`. Deterministic order: lexicographic.
- `KING_RAYS`, `KING_NEIGHBORS` — same leaper pattern as knight.

### `src/chess4d/pieces/king.py`

Same shape as knight. **Castling is NOT in this phase** (requires
castling rights, which is board-state we don't have yet). Normal king
moves only.

### Register in dispatch table

`_PIECE_GEOMETRY[PieceType.KING] = (KING_RAYS, KING_NEIGHBORS)`.

### Tests: `tests/test_king_adjacency.py` + `tests/test_king_moves.py`

- Interior mobility = 80 (§3.2 Lemma 1). Explicit on `{1,...,6}^4`.
- Corner (0,0,0,0): `3^4 - 1 - (truncation) = 15` (Chebyshev-1 within
  bounds from the corner). Verify.
- Neighbor set = all squares within Chebyshev distance 1. Property:
  `{sq2 for sq2 in KING_NEIGHBORS[sq]} == {sq2 for sq2 in ALL_SQUARES
  if sq.chebyshev_distance(sq2) == 1}`.
- Parity split (§3.8 Prop 2(iv)): of an interior king's 80 neighbors,
  exactly 40 preserve parity and 40 flip it. Verify.
- Standard friendly-blocks / enemy-captures / leaper-over-nothing (king
  has no intermediates).

Commit after 3C:
```
git add -A
git commit -m "Phase 3C: king Chebyshev-1 leaper (§3.9 Def 9)

Castling (§3.9 Def 10) deferred — requires castling-rights state.

Geometry: 80 nonzero displacements in {-1,0,+1}^4.
Generator: king_moves.
Dispatch: registered in _PIECE_GEOMETRY.
Tests: interior mobility 80, corner mobility 15, Chebyshev-1 equivalence,
parity 40/40 split."
git push
```

## Sub-phase 3D — Pawn (§3.10, Definitions 11-14)

**Expected effort: large. Only piece with color-dependent behavior and
axis parameterization.**

### Core design decision: pawn geometry is NOT in the dispatch table

The dispatch table assumes "piece type → one geometry." Pawns violate
this in three ways:

1. Forward direction depends on color (white goes +y/+w, black goes
   -y/-w). Two geometries per axis orientation.
2. Moves differ from captures (forward vs. diagonal).
3. Two-step initial moves depend on rank (y=1 for white Y-pawn, y=6
   for black Y-pawn, in 0-based).

Do **not** force pawns into `_PIECE_GEOMETRY`. Add a separate branch
in `Board4D.push` that dispatches to a pawn-specific validator when
`piece.piece_type is PieceType.PAWN`. The rest of the dispatch table
stays clean.

### Geometry additions to `src/chess4d/geometry.py`

Precomputed tables keyed by `(color, pawn_axis)`:

- `PAWN_FORWARD_MOVES: dict[tuple[Color, PawnAxis], Mapping[Square4D,
  tuple[Square4D, ...]]]` — the forward move squares (one-step always,
  two-step only from the pawn's starting rank). Empty tuple if the
  pawn is on the promotion rank (no forward move; promotion moves come
  from capturing or from the one-step if it lands on the boundary, but
  the paper's Definition 12 lists only one-step/double-step forward
  moves — a pawn reaching the boundary via those is where promotion
  happens).
- `PAWN_CAPTURES: dict[tuple[Color, PawnAxis], Mapping[Square4D,
  tuple[Square4D, ...]]]` — the two diagonal capture squares (one
  coord in the forward axis, one in x-axis with ±1).

Starting ranks (0-based):
- White Y-pawn: `y == 1`
- White W-pawn: `w == 1`
- Black Y-pawn: `y == 6`
- Black W-pawn: `w == 6`

Promotion ranks (0-based):
- White Y-pawn: `y == 7`
- White W-pawn: `w == 7`
- Black Y-pawn: `y == 0`
- Black W-pawn: `w == 0`

### `src/chess4d/pieces/pawn.py`

`pawn_moves(origin, color, board)` must consult the piece at `origin`
to get the `PawnAxis` (pawn_moves cannot infer orientation from color
alone — need the actual piece). Signature:

```python
def pawn_moves(origin: Square4D, color: Color, board: Board4D) -> Iterator[Move4D]:
    piece = board.occupant(origin)
    if piece is None or piece.piece_type is not PieceType.PAWN:
        raise ValueError(f"No pawn at {origin}")
    axis = piece.pawn_axis  # non-None by __post_init__ invariant
    ...
```

Move types:
1. **One-step forward**: if `forward_sq` is in-bounds and empty.
2. **Two-step forward**: if pawn is on its starting rank, both
   `forward_sq` and `forward_forward_sq` are empty.
3. **Captures**: for each of the two diagonal capture targets, if
   occupied by an opposing piece.
4. **Promotion**: if the forward or capture lands on the promotion
   rank, yield four `Move4D` with `promotion ∈ {ROOK, BISHOP, KNIGHT,
   QUEEN}` (not PAWN, not KING). Emit all four — caller selects.
5. **En passant**: OUT OF SCOPE for Phase 3D. Requires en-passant
   target state which doesn't exist yet.

### Push/pop for pawns

In `Board4D.push`, before the dispatch-table lookup:

```python
if piece.piece_type is PieceType.PAWN:
    self._push_pawn(move, piece)
    return
```

`_push_pawn` validates the move by regenerating legal pawn moves and
checking membership, then applies it. If `move.promotion` is set and
the to-square is on the promotion rank, replace the pawn with a new
`Piece(color=piece.color, piece_type=move.promotion)` at `to_sq`
(no `pawn_axis` — promoted piece is not a pawn).

Undo record for pawn moves: `(move, captured, original_piece)` — the
extra field captures the pre-promotion pawn so `pop()` can restore it.
This changes the undo stack shape slightly; adjust `pop()` to unpack
correctly for both pawn and non-pawn entries. Use a tagged tuple or
small dataclass — whatever's cleanest.

### Tests: `tests/test_pawn_adjacency.py` + `tests/test_pawn_moves.py`
+ `tests/test_pawn_promotion.py`

- One-step forward moves: Y-pawn at (3,3,3,3), white, advances to
  (3,4,3,3).
- Two-step forward from starting rank: white Y-pawn at (3,1,3,3)
  can move to (3,3,3,3); same pawn at (3,2,...) cannot two-step.
- Blocked forward: forward square occupied → no forward moves of
  either length.
- Two-step blocked by intermediate: (3,1,3,3) → (3,3,3,3) blocked by
  a piece at (3,2,3,3).
- Diagonal capture: white Y-pawn at (3,3,3,3), enemy at (4,4,3,3) —
  capture legal, forward still legal if unblocked.
- No forward capture: enemy at (3,4,3,3) — forward move is blocked,
  NOT a capture.
- Axis parameterization: W-pawn at (3,3,3,3), white, advances to
  (3,3,3,4) (not y-direction). Same test pattern as Y-pawn but axis=W.
- Black pawn directions: black Y-pawn at (3,6,3,3) advances to
  (3,5,3,3) (negative y).
- Promotion emission: white Y-pawn at (3,6,3,3) advancing to (3,7,3,3)
  emits 4 moves, one per promotion type.
- Promotion with capture: white Y-pawn at (3,6,3,3), enemy at
  (4,7,3,3), emits 4 capture-promotion moves.
- Push+promotion: applying a promotion move replaces the pawn with the
  specified piece type, no `pawn_axis`.
- Pop-after-promotion: undo restores the pawn with its original
  `pawn_axis` intact.
- Property test: every generated pawn move from a random origin/color
  satisfies the per-axis forward or diagonal shape.

Commit after 3D:
```
git add -A
git commit -m "Phase 3D: pawn with axis/color-dependent moves and promotion

Pawn is the only piece with color-dependent geometry and axis-
parameterized rule logic; dispatched separately from _PIECE_GEOMETRY.

Geometry: PAWN_FORWARD_MOVES and PAWN_CAPTURES keyed by (color, axis).
Generator: pawn_moves — one/two-step forward, diagonal captures,
promotion-move emission (4 per promoting move).
Push/pop: _push_pawn branch handles promotion (replaces piece) and
undo (restores original pawn).

En passant deferred — requires en-passant target state.
Castling rights deferred (not a pawn concern, noted for tracking).

Paper: §3.10 Def 11-14."
git push
```

## After all four sub-phases

Final verification before wrapping:
- `pytest -v` — all tests pass, report total count
- `mypy --strict src/chess4d` — clean
- `ruff check src tests` — clean
- Smoke: 40-move mixed-piece game (rook, bishop, knight, king, pawn,
  queen, promotion), push all, pop all, report bit-identical state

Then:
```
git log --oneline
```

Report the commit SHAs for all four sub-phase commits, and a short
reflection: did the dispatch table hold up for queen+knight+king? Did
anything need refactoring that wasn't planned?

## Request before starting 3A

Show me:
1. The proposed signatures / geometry shapes for 3A (queen), 3B (knight),
   and 3C (king) in one batch — just the public API, before
   implementation.
2. Whether you plan to factor a shared `_slide_generator` or
   `_leaper_generator` helper, and the tradeoff you see.
3. The 3D pawn signature including the per-(color, axis) geometry
   table structure, and how you'll modify the undo stack entry shape.

I want to sign off on the architecture before you run the full batch.