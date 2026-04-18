# Maintenance pass — Phase 5 interaction regression coverage

## Why this, why now

`tests/test_phase5_smoke.py` currently has 4 scenarios — the planned
ones from Phase 5E. They cover "each feature works when combined with
the initial position," which is the right thing to verify when the
feature is new. What they do **not** cover is two-feature collisions:
situations where a bug would only surface because feature X and
feature Y are interacting, not because either is broken on its own.

Phase 6 (performance) is about to introduce incremental Zobrist
hashing, attack-map caching, and possibly batched legality queries.
Every one of those touches the hot path of `push` / `pop` /
`legal_moves` — exactly the surface where two-feature-collision bugs
hide. Adding regression coverage **now**, before Phase 6 starts,
means:

- Any performance refactor that breaks a corner case fails a specific
  named test instead of a vague "something got slower by being wrong."
- The cost is paid once, in isolation, instead of smeared across the
  Phase 6 session where we'd be debugging "is this a perf bug or a
  correctness bug?"
- Existing coverage (388 tests) doesn't need to change; this is
  purely additive.

**Expected effort:** small-to-moderate. Roughly 15-25 new tests
across the Phase 5 feature pairs, no new source code. Session should
run well under an hour of agent work.

## Before starting: confirm Phase 5 state

```
git log --oneline -8
```

Expected top of history: `9ea44d8` (Phase 5E smoke), `c6ef246`
(Phase 5D zobrist), `387e3ab` (Phase 5C clock), `23840c2` (Phase 5B
ep), `4c76388` (Phase 5A castling).

```
git status
```

Should be clean.

/plan

## Scope: interaction coverage only

This pass is **purely tests**. No source changes. If a test reveals a
bug, stop, report the bug, and wait for direction — don't fix it
speculatively during the maintenance pass. A correctness bug in
Phase 5 features is a Phase 5 bug to triage separately, not something
to quietly patch under the banner of "adding tests."

All new tests land in `tests/test_phase5_interactions.py` (a new
file). Do not edit `test_phase5_smoke.py` — its four scenarios are
the "each feature in isolation" tests and should stay that way for
documentation purposes.

## The interaction matrix

Five Phase 5 features: castling, en passant, halfmove clock,
threefold repetition, check/legality. The pairs we care about are
the ones where **one feature's state transition could plausibly
affect the other's correctness**. Not all 10 pairs are interesting;
these are:

### A. Castling × En passant

- **Castling after a two-step pawn advance.** White pushes a pawn
  two squares (setting ep_target); black castles. Verify: ep_target
  is correctly cleared by black's castling (castling is not a pawn
  move and not a capture, so it clears ep state like any other
  non-two-step move does). Verify the castling itself is otherwise
  unaffected.

- **Two-step pawn advance followed by castling undo.** Push a pawn
  two-step (sets ep state), push a castling move (clears ep state
  and mutates rights), pop the castling move. Expected: ep state is
  restored, castling rights restored, board bit-identical.

- **En passant capture that removes a rook's home-square protector.**
  Construct a narrow case where a rook at its home square relies on
  some defender, and an en-passant capture on an adjacent diagonal
  removes that defender — specifically test that this does *not*
  incorrectly clear the rook's castling right. En passant only
  revokes rights when the captured piece is itself a home-square
  rook, which pawns never are. This is a confirmation test.

### B. Castling × Halfmove clock

- **Castling does not reset the clock.** Castling is neither a pawn
  move nor a capture, so the halfmove clock should increment, not
  reset. Set the clock to some nonzero value via previous moves,
  castle, verify clock = previous_clock + 1.

- **Castling undo restores clock exactly.** Push a castling move
  from a state with halfmove_clock = N; verify clock = N+1 after;
  pop; verify clock = N.

### C. Castling × Threefold repetition

- **Castling rights affect position hash.** Two states with
  identical placement but different castling rights must hash
  differently. This is already covered by `test_zobrist.py` in
  principle; here we test the *game-flow* version: reach an
  identical placement twice, once before castling was available and
  once after rights have been revoked (without castling occurring —
  just from a king's earlier move), and verify the position_history
  counts do *not* treat them as the same position.

- **Castling then mirror-castling doesn't cause false repetition.**
  White castles kingside on slice S1; black castles kingside on
  slice S2. The positions reached are not three-repeats of any prior
  position even if the placement pattern looks symmetric, because
  castling rights shifted.

### D. En passant × Halfmove clock

- **En-passant capture resets the clock.** The capturing pawn move
  is both a pawn move and a capture; both reset. Verify clock = 0
  after an en-passant capture regardless of its prior value.

- **En-passant undo restores clock.** Set up a clock value N, push
  an en-passant capture (clock now 0), pop, verify clock = N.

### E. En passant × Threefold repetition

- **En-passant target changes the hash.** This is the FIDE-standard
  subtle case: two placements identical except one has an
  ep_target set. The hash should differ. Specifically: reach a
  position via a pawn two-step (ep target set); reach the *same*
  placement later without a two-step having just occurred (ep
  target is None). These positions must hash differently.

- **En passant that expires does not cause false repetition.** A
  two-step sets ep state; the next ply (not taking the en passant)
  clears it; if play later returns to the *placement* that existed
  after the two-step, but without ep state set, those are different
  positions and repetition counting must not conflate them.

  This is a subtle case and worth writing carefully: the hash must
  include ep_target, which the existing implementation does. The
  test confirms that behavior holds under game flow, not just
  pair-wise hash comparison.

### F. Check × Castling

- **King in check cannot castle.** Standard rule (§3.9 Def 10
  clause 4). Construct a position where castling would otherwise be
  legal but the castling king is in check; verify the castling move
  is rejected with `IllegalMoveError`.

- **King cannot castle through an attacked square.** §3.9 Def 10
  clause 3 — the transit path must be safe from attackers on *any*
  slice, not just the castling slice. Construct a position where
  the king is not in check and the destination is not attacked, but
  the intermediate square is attacked by a piece on a different
  `(z', w')` slice. Verify rejection.

- **King cannot castle into check.** The destination square is
  attacked. Verify rejection.

- **Castling legality is not cached across state.** Push a move
  that puts the opponent's king position in a state where the
  opponent *could* castle, then push an opponent non-castling
  move. The castling right for the opponent still exists in
  `castling_rights`. Now push another move that causes an attacker
  to threaten the opponent's intermediate square. Verify that a
  subsequent castling attempt is rejected — i.e., castling legality
  is re-evaluated per-call, not inherited from when the right was
  granted.

### G. Check × En passant

- **En-passant capture that leaves own king in check is illegal.**
  A pawn pinned by an enemy slider cannot capture en passant if
  doing so would expose its own king. This is the standard "pinned
  pawn" case generalized to en passant. Construct a position: white
  king on some square, white pawn on an adjacent file, black slider
  along the king's axis with the white pawn as the only blocker.
  Black two-step-advances an adjacent pawn (sets ep_target). The
  white pawn *geometrically* can en-passant capture but doing so
  would remove itself from the pin and expose the white king.
  Verify the en-passant capture is filtered out of `legal_moves`.

- **En passant gives check.** An en-passant capture that results in
  the capturer attacking the enemy king. Verify the capture is
  legal (no self-check) and that `in_check(enemy_side)` is True
  after the push.

### H. Check × Threefold repetition

- **Checkmate and threefold repetition are independent predicates.**
  Construct a position where `is_threefold_repetition()` is True and
  `is_checkmate()` is also True (or at least: verify the two
  predicates don't interact — one doesn't accidentally suppress the
  other). A player in checkmate has no legal moves, so they couldn't
  reach a threefold-repetition state *by moving*; but the position
  they're in at the moment of checkmate might itself be a
  three-repeat if the same position arose before. Verify both
  predicates return True independently.

- **A check in one of the repetition occurrences still counts.** A
  position where the king is in check can be a "repeat" just like
  any other — the rules don't exclude check positions from
  repetition counting. Set up a cycle that passes through a checked
  position three times; verify threefold triggers.

### I. Clock × Threefold repetition

- **Fifty-move and threefold are independent.** Positions where
  both trigger; verify both predicates fire.

- **Pawn move resets clock but doesn't disrupt repetition counting.**
  The clock and the history are independent fields; a pawn move
  resets the clock but only *changes* the position (which naturally
  changes the hash and terminates any existing repetition cycle).
  Verify the clock reset is orthogonal — no spurious history
  truncation.

## Additional regression coverage not strictly "interactions"

### J. Undo-stack depth stress

- **Long alternating-castle sequence with undos.** Push 20 castling
  moves (across different slices), pop all 20, verify bit-identical
  state across all five Phase 5 fields and the board. This is the
  undo-stack-at-depth test that Phase 5's own tests don't cover.

- **Interleaved en-passant and normal pushes with full unwind.**
  Push 10 moves with an en-passant capture somewhere in the middle,
  pop all 10, verify everything restored.

### K. Rights-revocation edge cases

- **Rook moves to and from home square.** A rook moves away from
  its home square (revokes right), moves back (right stays
  revoked). Verify this — the right revocation is permanent, not
  triggered by "rook not at home right now."

- **Captured-rook replacement.** Rook at home is captured (revokes
  right), captured pawn is promoted to a rook at the *same square*
  later. Verify the right stays revoked — promotion doesn't grant
  castling rights to the new rook. This is the Oana-Chiru analog
  of "promoted rook doesn't restore castling" in 2D chess.

### L. Hypothesis property: push-pop under all Phase 5 features

One property test that:
- Generates a random sequence of 5-15 legal moves from the initial
  position (most will be ordinary pushes; castling and en passant
  will be rare by random sampling but will occur).
- Pushes all, pops all.
- Asserts: board equal, castling_rights equal, ep state equal,
  halfmove_clock equal, position_history equal, side_to_move equal.

This is the strongest property-test guarantee that Phase 5's undo
stack is sound. Set `max_examples=30`, `deadline=None`, and
`suppress_health_check=[HealthCheck.function_scoped_fixture]`.

**Note on performance:** this test will be slow because each
generated move requires a `legal_moves()` call, which is the 7s hot
path. The test is acceptable at ~3-5 minutes total for 30 examples;
if it's dramatically slower, cut max_examples to 10 and mark it
`@pytest.mark.slow` with a pytest marker configured in
`pyproject.toml` to skip by default.

## Deliverables

One new file: `tests/test_phase5_interactions.py` with sections A-L
from above. Aim for 20-30 tests total. Section L (Hypothesis) is one
test with property-test semantics.

Do **not** modify:
- Any source file in `src/chess4d/`.
- Any existing test file.
- `pyproject.toml` (except to add the `slow` marker if Section L
  needs it, and only if necessary — we're prefer-not to slow the
  default test run).

## Gates after the session

```
pytest -v                         # expect ~408-418 tests (388 + 20-30 new)
mypy --strict src/chess4d         # no changes here, should still pass
ruff check src tests              # new tests must pass ruff
git diff --stat HEAD~1..HEAD      # verify only tests/ changed
```

## Commit

After all tests pass:

```
git add -A
git commit -m "Phase 5 regression tests: feature-interaction coverage

Adds tests/test_phase5_interactions.py covering pair-wise interactions
between castling, en passant, halfmove clock, threefold repetition,
and check/legality. Also covers undo-stack depth stress, rights-
revocation edge cases (rook returning home, promoted-rook rights),
and a Hypothesis property test exercising push-pop soundness across
all Phase 5 state fields.

No source changes. Prepares the library for Phase 6 performance work
by establishing correctness regression coverage before the hot path
gets refactored."
git push
```

## Request before writing tests

Show me:

1. **Your proposed test scenarios for sections F (Check × Castling)
   and G (Check × En passant)** — specifically the position setup.
   These are the most geometrically involved cases and the ones
   where a poorly-constructed test would pass or fail for reasons
   unrelated to the feature being tested. I want to see the setup
   positions before the asserts are written.

2. **Your decision on Section L's performance strategy.** Will the
   hypothesis test run as part of the default `pytest` invocation,
   or will it be marked slow? If marked slow, how does the
   configuration look in `pyproject.toml`?

3. **Any test from sections A-L that you think is redundant with
   existing coverage.** If something I listed here is already
   covered by Phase 5's own tests, skip it and tell me why. The
   goal is new coverage, not duplication.