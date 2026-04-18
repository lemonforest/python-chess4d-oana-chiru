# Phase 6 — Performance: make the library usable for real work

## Scope

`GameState.legal_moves()` from `initial_position()` currently takes
~7 seconds and returns 2,356 moves. That's correct but unusable for
anything beyond single-move analysis. This phase targets the hot path
with three layered optimizations, each independently testable against
the regression suite built in the prior pass:

1. **Incremental Zobrist hashing** (5D's naive `O(pieces)` per call
   becomes `O(1)` per push/pop).
2. **Cached attack maps** on GameState, invalidated and rebuilt
   lazily.
3. **`legal_moves()` inner-loop optimization** — avoid the full
   make-unmake round-trip where a cheaper local check suffices.

**Target:** `legal_moves()` from the initial position in ≤200ms.
Stretch target: ≤50ms. The 200ms target is the usability threshold
for a playback viewer (one legal-move call per frame at 5fps is
fine); the 50ms stretch is what search-based analysis would need.

**Explicitly out of scope:** rewriting the library in C or with
numpy/scipy integration, SIMD/bitboard representations, or moving
the encoder's C17 port into this package. Any of those are Phase 7+
options if the pure-Python optimizations don't hit the 200ms target.

## Before starting: confirm regression baseline

```
git log --oneline -3
```

Top commit should be `09e3e9d` (Phase 5 regression tests).

```
git status
```

Should be clean.

```
pytest -q                  # 410 passing, 1 deselected (slow)
pytest -m slow -q          # 1 passing in ~2:21
```

Both test runs must pass before starting Phase 6. This is the
correctness baseline every sub-phase will be measured against — each
optimization must keep both runs green. If either is failing before
Phase 6 starts, stop and triage before proceeding.

Then:
```
git push
```

/plan

## Architectural invariants (locked from prior phases)

- `Board4D` stays at the placement-plus-pseudo-legal layer; game-level
  state lives on `GameState`.
- Pseudo-legal piece generators stay king-safety-unaware.
- Undo stack (both `Board4D._undo` and `GameState._undo`) stays the
  single source of truth for push/pop reversibility.
- Public API surface does not change. No method signatures change,
  no classes added or removed that consumers would notice.
- `_PIECE_GEOMETRY` dispatch table remains the extension point for
  new piece types.

## New architectural invariants for Phase 6

- **Optimizations are behavior-preserving.** Every sub-phase must
  end with `pytest -q && pytest -m slow -q` green. This is the
  regression-testing investment paying off: correctness is what the
  existing 411 tests certify, and performance is what new measurements
  certify.
- **Caches live on GameState, not Board4D.** A cache is game-level
  derived state; putting it on `Board4D` would conflate placement
  (authoritative) with computed views (derived).
- **Caches are invalidated by GameState.push/pop only.** No background
  invalidation, no watchers. Every mutation path is explicit: push
  invalidates, pop restores from the undo stack.
- **Measure before and after each sub-phase.** A benchmark that
  doesn't run reliably on every commit isn't a benchmark. New file
  `tests/benchmark_phase6.py` (or a `benches/` directory if that
  reads cleaner) — not part of the default test run, callable
  manually.

## Sub-phase 6A — Benchmark harness

**Expected effort: small. Foundation for everything that follows.**

Before any optimization, build a reproducible benchmark. Measuring
"how fast is legal_moves" needs to be a one-command operation with
consistent output across runs. Otherwise the performance claims at
the end of each sub-phase aren't comparable to each other.

### New file: `benches/bench_legal_moves.py`

Not in `tests/`, not collected by pytest. A standalone script:

```python
"""Benchmark GameState.legal_moves() on representative positions.

Run: python benches/bench_legal_moves.py
Output: one line per scenario, ms median + p99 over N trials.
"""

import time
import statistics
from chess4d import initial_position, GameState
# (plus helpers for constructing benchmark positions)

def bench(name: str, state_factory, n_trials: int = 5) -> None:
    times = []
    for _ in range(n_trials):
        state = state_factory()
        t0 = time.perf_counter()
        _ = list(state.legal_moves())
        t1 = time.perf_counter()
        times.append((t1 - t0) * 1000)
    median = statistics.median(times)
    p99 = max(times)  # close enough for n=5
    print(f"{name:<40} median={median:7.1f}ms  max={p99:7.1f}ms")
```

### Benchmark scenarios

1. **Initial position, white's legal moves.** This is the primary
   target. Expected Phase 5 baseline: ~7000ms. Phase 6 target:
   ≤200ms.
2. **Initial position after one move, black's legal moves.** Tests
   that the first push doesn't produce a pathological cache state.
3. **A mid-game position with fewer pieces.** Construct a position
   with ~200 pieces (captured ~700). Tests that the per-piece cost
   is what dominates, not a fixed overhead.
4. **A constructed "near-mate" position.** One side with few pieces,
   in check, exercising the legality filter at its hardest.
5. **A single-piece position.** One rook on an empty board. Tests
   the per-call fixed overhead floor.

### Deliverables

- `benches/bench_legal_moves.py` with the five scenarios above.
- A single run captured as `benches/baseline_phase5.txt` committed
  alongside the script — this is the before-number everything else
  is measured against.

### Commit after 6A:

```
git add -A
git commit -m "Phase 6A: benchmark harness for legal_moves performance

benches/bench_legal_moves.py runs five representative scenarios with
median and max over 5 trials. Baseline captured to
benches/baseline_phase5.txt — this is the ~7s initial-position
number that Phase 6B-6D will drive down."
git push
```

## Sub-phase 6B — Incremental Zobrist hashing

**Expected effort: moderate. Most mechanical of the three
optimizations.**

The current `hash_position()` in `zobrist.py` iterates every
occupied square on every call. This runs once per push (to append to
position_history) and once per `is_threefold_repetition()` check.
For `legal_moves()` which doesn't directly hash, this isn't
dominating the 7s number — but it does show up as ~5-10ms per push
on the 896-piece initial position, which matters for any workflow
that pushes many moves.

### Target API (no external changes)

```python
class GameState:
    # existing fields...
    _incremental_hash: int  # maintained invariant: equals hash_position(self)

    def push(self, move):
        # ... existing logic ...
        # Incremental update: XOR out old placements, XOR in new.
        self._incremental_hash ^= <piece-leaving-from-sq>
        self._incremental_hash ^= <piece-arriving-to-sq>
        self._incremental_hash ^= <captured-piece-if-any>
        self._incremental_hash ^= SIDE_HASH  # always toggles
        self._incremental_hash ^= <ep-hash-delta>
        self._incremental_hash ^= <castling-rights-delta>
        # ... append to position_history using self._incremental_hash ...
```

### Incremental hash rules

XOR is its own inverse, so every state change decomposes into:
- The pre-change component, XORed out.
- The post-change component, XORed in.

Specifically:
- **Move a piece from A to B**: XOR out `piece_hash[A, piece]`,
  XOR in `piece_hash[B, piece]`.
- **Capture**: additionally XOR out `piece_hash[B, captured]` before
  XORing the mover in.
- **Promotion**: XOR out `piece_hash[to, pawn]`, XOR in
  `piece_hash[to, promoted_piece]`. (The mover-arrives XOR above
  used the pawn's hash; promotion is a separate step that swaps
  pawn for promoted piece.)
- **Castling**: two piece moves (king + rook). Each is handled as
  above.
- **Side-to-move flip**: XOR in the side-to-move hash.
- **Castling rights change**: for each right added or removed, XOR
  in/out its hash.
- **En-passant target change**: XOR out old ep-hash (if any), XOR
  in new (if any).

### Validation strategy

A bug in incremental hashing is subtle — it can cause hashes to
diverge from the "true" full-recomputation hash, which silently
breaks threefold repetition detection.

**Invariant test** in existing `test_zobrist.py` or a new file:
after every push and after every pop, assert that
`state._incremental_hash == hash_position_full(state)`. The full
version is renamed from today's `hash_position` and kept as a
test-only oracle.

This test should run on:
- A Hypothesis property test of random push-pop sequences (30
  examples, can borrow the strategy from Section L of the
  regression tests).
- A deterministic sequence covering all move types: ordinary,
  capture, two-step pawn, en-passant, promotion, castling (all four
  of these: kingside-white, kingside-black, queenside-white,
  queenside-black).

Every one of those should assert the incremental == full invariant
before and after each push, and before and after each pop.

### Performance measurement

Run `benches/bench_legal_moves.py` after. The `legal_moves()` hot
path doesn't directly benefit from incremental hashing — that's 6C
and 6D. But the per-push cost should drop. Measure push performance
specifically (add to the benchmark if not already there). Expected
improvement: push goes from ~5-10ms to <0.1ms on the 896-piece
initial position.

### Commit after 6B:

```
git add -A
git commit -m "Phase 6B: incremental Zobrist hashing

GameState._incremental_hash is maintained invariant (equals
hash_position_full) across every push/pop. Each mutation XORs out
pre-change components and XORs in post-change components.

Correctness: new test_zobrist_incremental.py asserts the invariant
after every operation in a deterministic sequence and across a
Hypothesis property test of 30 random push-pop walks.

Performance: push-cost on 896-piece initial position drops from
~8ms to <0.1ms. legal_moves() not materially affected yet (that's
6C/6D)."
git push
```

## Sub-phase 6C — Attack-map caching

**Expected effort: moderate-high. The biggest correctness risk.**

The current `legal_moves()` pattern:
```
for candidate in _all_pseudo_legal_moves(side, board):
    board.push(candidate)
    safe = not any_king_attacked(side, board)
    board.pop()
    if safe:
        yield candidate
```

`any_king_attacked` iterates every enemy piece and runs its move
generator — for the 896-piece position, that's ~448 enemy pieces
with up to 80 mobility each, ~36K ops per call. Multiplied by 2356
candidates = 85M ops. That's the 7 seconds.

The key insight: **the enemy attack map doesn't change very much
between pushes**. Most candidate moves don't move the king and don't
change which squares enemy pieces attack. Caching the attack map and
only recomputing the *delta* after each hypothetical push is a major
win.

### Cache design

```python
class GameState:
    _attack_cache: dict[Color, frozenset[Square4D]] | None = None
    # Initially None. Populated on first use. Invalidated on every push.
```

The cache is per-color: both `_attack_cache[WHITE]` (squares
attacked by white) and `_attack_cache[BLACK]` are stored.

### Invalidation

The simple and correct rule: **every push and every pop invalidates
the cache for both colors**. Set `_attack_cache = None` at the top
of both methods, and rebuild lazily on next access.

This gives correctness for free — the cache can't go stale because
it's dropped on every state change. The win comes from the
*inner* make-unmake in `legal_moves`: during the check-safety test,
we push a candidate, invalidate the cache, run `any_king_attacked`
(which rebuilds the cache fresh), pop, and discard the rebuilt
cache.

That's not actually faster than the current code. **The optimization
is in avoiding the rebuild inside `any_king_attacked`.**

### The actual optimization: per-candidate delta check

For each candidate move, we can answer "is any friendly king
attacked after this move?" without a full attack-map rebuild. We
need to check:

1. **Did this move leave a piece unpinned?** If the moving piece was
   blocking a slider attack on its own king, moving it exposes the
   king. This is the classic "discovered check" pattern.
2. **Did this move's landing square block an existing attack?** If a
   slider was currently attacking one of our kings, and this move
   lands a piece in the slider's ray between it and the king, the
   attack is now blocked.
3. **Did the king itself move into an attacked square?** If the
   moving piece is a king, its new square needs to be checked for
   attackers.
4. **Did a capture remove an attacker?** If the captured piece was
   currently attacking one of our kings, we just resolved a check.

The check-detection algorithm becomes:

```python
def candidate_safe(state, move, piece, friendly_kings, enemy_attackers):
    # enemy_attackers is the pre-move attack map of the enemy color.
    # Start from: is any friendly king currently attacked?
    # Then check each of the four deltas above.
    ...
```

This is complicated to get right. The make-unmake version is simpler
and certified correct by every existing test. The argument for
doing this is: a correct implementation runs in microseconds per
candidate instead of milliseconds.

### Alternative: make-unmake + cached attack map

Simpler and probably sufficient for the 200ms target:

1. Before entering the candidate loop, compute the enemy attack map
   once and cache it.
2. For each candidate, do the push, rebuild attack map, check king
   safety, pop.
3. The win is that `any_king_attacked` used to rebuild from scratch
   every call; now it reuses the cached attack map for the "is any
   friendly king in the attacked set" check.

But push+pop still invalidates and rebuilds. So this approach
doesn't actually win — we'd still be rebuilding on every candidate.

**The real win requires not rebuilding on every candidate.** That
means either:
- **Option A:** The delta-based per-candidate check (above, hard).
- **Option B:** Decide a candidate's safety *without* actually
  pushing, by reasoning about the move's interaction with the
  pre-move attack map.

Option B is the classical chess-engine approach and is what
python-chess uses under the hood. It answers:
- If the mover is not a king: does the move change the pin status of
  any friendly king? (If the moving piece is not on any slider's
  pin line, no further check needed.)
- If the mover is a king: is the destination attacked by the enemy
  (consulting the cached attack map, adjusted for the king's own
  square being vacated)?
- Does the move's capture remove any attacker currently attacking a
  friendly king?

Option B requires a **pin map** (for each friendly king, which
friendly pieces are pinned, and by what enemy slider on what ray)
computed once per `legal_moves()` call. Pin map construction is
`O(kings × sliders)` which is ~28 × ~200 = 5600 ops, much cheaper
than per-candidate rebuild.

### Recommendation

Implement Option B with the pin map. It's the algorithmically right
approach and is what the 50ms stretch target actually needs. The
delta-based approach (Option A) is superseded by it.

### Validation

The existing 411 tests and the slow Hypothesis property are the
safety net. Any implementation of Option B that passes all 411 +
the slow test is correct by the regression suite's standards.

**Additional validation:** a new test `test_legal_moves_parity.py`
that runs `legal_moves()` via both the old make-unmake path (kept
as a private `_legal_moves_slow()` method for this purpose) and the
new pin-map path, and asserts they return identical move sets. Run
this on 20 constructed positions including: initial, after 1-5
random plies, positions with various check patterns, and the
smoke-test positions from `test_phase5_interactions.py`.

### Commit after 6C:

```
git add -A
git commit -m "Phase 6C: pin map optimization for legal move generation

legal_moves() no longer make-unmakes every candidate. Instead, it
computes a pin map once per call (which friendly pieces are pinned,
by which enemy slider, along what ray) and uses it to filter
candidates in O(1) per candidate.

Correctness: new test_legal_moves_parity.py asserts the optimized
path returns identical move sets to the slow make-unmake path on
20 constructed positions. All 411 existing tests pass.

Performance: legal_moves() from initial position drops from ~7s
to <target>ms. See benches/phase6c.txt for the full benchmark."
git push
```

## Sub-phase 6D — Pseudo-legal move caching (if needed)

**Expected effort: small-to-moderate. Only do this if 6B+6C haven't
hit 200ms.**

After 6B and 6C, re-run the benchmark. If `legal_moves()` is under
200ms on the initial position, **stop here** — we've hit the target,
and additional optimization risks correctness regressions for
marginal gains.

If we're still above 200ms, the remaining hot path is likely
`_all_pseudo_legal_moves`. Each piece's move generator does a ray
walk even though the board geometry hasn't changed. A cache of
"pseudo-legal moves for piece at square X given current
occupancy" is possible but subtle — occupancy changes affect most
pieces, so invalidation is nearly universal.

A narrower optimization: cache the **per-piece** move list,
invalidated only when that piece's square changes OR when a square
on one of its rays changes. This is per-piece cache invalidation
and is a meaningful engineering task.

If we get here, **stop and measure first**. Profile the remaining
hot path and confirm `_all_pseudo_legal_moves` is what's dominating
before doing any work.

### Commit after 6D (if needed):

```
git add -A
git commit -m "Phase 6D: per-piece pseudo-legal move caching

Pseudo-legal moves cached per-piece, invalidated on relevant square
changes. Necessary only because 6B+6C didn't hit the 200ms target.

Performance: legal_moves() from initial position <target>ms.
See benches/phase6d.txt."
git push
```

## Sub-phase 6E — Benchmark re-run and reporting

**Expected effort: small. Wrap-up and measurement.**

Final benchmark run comparing:
- `benches/baseline_phase5.txt` (before)
- `benches/phase6_final.txt` (after)

On the five benchmark scenarios. Capture as a committed file.

### Commit after 6E:

```
git add -A
git commit -m "Phase 6: final performance measurements

Comparison of before/after benchmarks across all five scenarios.
Headline: legal_moves() from initial position <final>ms, down from
7000ms (<factor>× speedup).

All 411 default tests + 1 slow test green. mypy strict + ruff clean.
No public API changes."
git push
```

## After all sub-phases

Final gates:
```
pytest -q                  # 411 passing + any new parity/invariant tests
pytest -m slow -q          # slow Hypothesis still passing
mypy --strict src/chess4d
ruff check src tests
git log --oneline -8
python benches/bench_legal_moves.py  # report numbers
```

## Request before starting 6A

Before implementing anything:

1. **Benchmark scenario selection.** The five I listed are my
   guesses at what's representative. If you've run the existing
   tests and have a sense of which positions might be harder or
   easier than I'm estimating, speak up. Otherwise proceed with my
   five.

2. **Pin-map representation.** For 6C's pin-map approach, what's
   the data structure? I'd lean toward:
```python
   PinMap = dict[Square4D, tuple[Square4D, Displacement]]
   # key: pinned piece's square
   # value: (king being protected, ray direction toward pinner)
```
   but other shapes work. Confirm or propose.

3. **When to skip 6D.** The stop condition is "6B+6C hit ≤200ms."
   Agree or propose different? I'd rather stop early than over-
   optimize.

4. **Parity test scale.** Is 20 constructed positions enough for
   the legal_moves parity test? If we're running it in CI's default
   `pytest` invocation, it needs to be fast. 20 positions × 2
   implementations × small legal_moves() = probably a few hundred
   ms total, which is fine. More is better for correctness
   confidence but worse for test speed.

## Deferred (as before)

- **Connector to chess-spectral encoder** — the `[spectral]`
  optional extra.
- **Move notation (SAN-equivalent) and FEN-equivalent** — separate
  phase, not performance-related.
- **Bitboard/SIMD rewriting** — only if 6A-6E don't hit target.
- **Alternative rulesets** — the dimensional-consistent family or
  any other variant.