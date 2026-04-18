# Phase 5 — Castling, en passant, draw detection

## Scope

Three features, one unifying theme: **rules that require state beyond
placement and side-to-move**. Each introduces a new piece of game
history that the board didn't need to know about until now.

- **Castling** (§3.9 Def 10) needs castling rights — per-side,
  per-rook-and-king tracking of whether either has moved.
- **En passant** (§3.10 Def 15) needs an en-passant target — a
  transient square (at most one per position) where the last-moved
  pawn can be captured on the next ply.
- **Draws** need two new counters: the halfmove clock (50-move rule)
  and a repetition hash history (threefold repetition).

Batched together because they share the same architectural concern:
**state lives on `GameState`, not `Board4D`**. Adding them piecewise
would mean three rounds of "extend GameState, update push/pop, add
undo-stack fields, propagate through legal_moves." Doing them once
keeps the state-model refactor to a single pass.

**Explicitly not in this phase:** performance work on `legal_moves`
(7.4s from the starting position is a known issue, documented at the
end of this plan). Phase 6 will target that.

## Before starting: commit Phase 4 state and enter plan mode

Phase 4 shipped three commits on `foxglove` (4A/4B/4C merged from the
planned 4A-4E sub-phases; the work is all there, just fewer commit
boundaries than originally specified):

```
git log --oneline -8
```

Expected top commits: `768b7c5` (startpos), `dfcaa25` (GameState +
legality), `0752337` (attack primitives), then the Phase 3 commits.

```
git status
```

Should be clean or have only incidental changes.

```
git push
```

Confirm `foxglove` is up to date before proceeding.

/plan

## Architectural invariants (locked from prior phases)

- `_PIECE_GEOMETRY` dispatch table for sliders/leapers; do not add
  elif chains.
- Pawn geometry bypasses the dispatch table via `_push_pawn`.
- Pseudo-legal generators do not check king safety; legality lives in
  `GameState.push` and `GameState.legal_moves`.
- `Board4D` stays at the placement layer; anything that needs game
  history lives on `GameState`.
- Undo-stack entries are tuples appended by `Board4D.push` variants
  and consumed by `Board4D.pop`. Phase 5 extends the *GameState*
  undo stack (separate from Board4D's), not the board's.
- Paper 1-based → code 0-based conversion happens only at UI
  boundaries.

## New architectural invariants for Phase 5

- **GameState owns castling rights, en-passant target, halfmove
  clock, and position history.** Board4D stays placement-only. The
  division of labor: `Board4D` knows "what piece is where"; `GameState`
  knows "what rights, clocks, and history apply."

- **GameState.push manages its own undo stack** (separate from
  `Board4D._undo`). Each GameState push records the prior values of
  the new state fields before mutating them; pop restores them. This
  avoids threading new fields through `Board4D.push`'s signature,
  which stays pseudo-legal-only.

- **Repetition hashing must be order-independent of placement but
  include castling rights and en-passant target.** A position that
  can be reached via different move orders must hash to the same
  value; two placements that look identical but differ in castling
  rights (one side has castled, the other hasn't but their king is
  back on its square) must hash differently. Use Zobrist-style XOR
  hashing (paper §4.7) with a fixed seed.

- **50-move clock resets on pawn moves and captures.** Both are
  standard chess rules; the paper inherits them by reference.

## Sub-phase 5A — Castling rights + castling move

**Expected effort: moderate. Rights-tracking plus one new move type.**

### Castling scope under Oana-Chiru (§3.9 Def 10)

Castling is restricted to the X-axis within a single `(z, w)`-slice.
The king and rook involved must both be unmoved; all squares strictly
between them must be empty; the king must not be in check before the
move; every square the king traverses (including the destination)
must not be attacked by any piece from *any* `(z', w')` slice — the
attack constraint is **global**, not slice-local.

### Castling-rights representation

With ~28 kings per side and ~56 rooks per side (1 per back rank × 56
slices), castling rights is `dict[(Color, Square4D), bool]` where
the square identifies the rook's starting square. Each entry tracks
whether the associated rook has moved; the king for a given slice is
tracked by *each of its eligible rooks* separately (kingside and
queenside each need their own right). This is more bookkeeping than
in 2D chess but follows directly from the paper.

**Simpler alternative worth considering:** since each (color, slice)
has one king and two back-rank rooks, and all three must be unmoved
for castling to be legal on that slice, a `frozenset` of "still
eligible" (color, slice, side) triples is cleaner:

```python
CastlingRight = tuple[Color, int, int, CastleSide]  # (color, z, w, side)
# where CastleSide is KINGSIDE (x=7 rook) or QUEENSIDE (x=0 rook)
```

and a position has a `frozenset[CastlingRight]` of currently-eligible
castles. Pick one representation; stick with it.

### State additions to GameState

```python
@dataclass
class GameState:
    board: Board4D
    side_to_move: Color
    castling_rights: frozenset[CastlingRight]
    # (existing fields from Phase 4)
```

`GameState.push` must:

1. Detect if the move is a castling move (`move.is_castling = True`);
   validate all preconditions (§3.9 Def 10 numbered list).
2. For non-castling moves, revoke any castling rights the move
   invalidates: moving a king revokes both its slice's castling
   rights; moving or capturing a back-rank rook revokes that rook's
   right; rook being captured on its home square also revokes.

### Castling-move validation

A castling move has `is_castling=True` and move.from_sq is a king's
square on some `(z, w)`-slice. Validate:

1. The castling right for this (color, slice, side) is in
   `castling_rights`.
2. All squares between the king and rook on the X-axis are empty.
3. King is not in check (`any_king_attacked(side, board)` is False
   *before* the move).
4. The king's transit path — its start, the intermediate square, and
   its destination — contains no square attacked by any enemy piece
   from any slice.

Then apply: king moves two squares toward the rook along X; rook
moves to the square immediately adjacent to the king on the opposite
side. The move is a *compound* mutation of two pieces on the board;
encode this carefully in the undo stack.

### Move encoding

`Move4D` already has `is_castling: bool`. The from_sq is the king's
square; the to_sq is the king's destination. The rook's movement is
derived from the from_sq and to_sq by the castling rule (king moves
2 toward rook → rook crosses to the other side of the king). This
keeps Move4D's shape stable.

### Undo for castling

The GameState undo-stack entry for a castling move needs to record:
- The prior castling_rights set (before rights were revoked).
- The prior side_to_move.
- A note that this was a castling move (so pop knows to move both
  pieces back, not just one).

The board's own undo stack will get a two-move sequence (king move,
rook move) or a single compound entry — pick the implementation that
keeps `Board4D.pop` clean. Probably: `GameState.push` for a castling
move calls `Board4D` twice via a new internal `_push_raw(move)` that
skips legality (castling has already validated everything), and
`GameState.pop` reverses via two `Board4D.pop` calls. This keeps the
compound-move structure at the GameState layer.

### Tests: `tests/test_castling.py`

- Castling-rights initial state at `initial_position()`: every back-
  rank king and both of its rooks per populated slice has rights.
  Verify the frozenset has the expected cardinality (4 central slices
  × 2 colors × 2 sides + 24 white-only × 2 sides + 24 black-only × 2
  sides = 112 castling rights).
- Moving a king revokes that slice's castling rights for that color
  (both sides).
- Moving a rook revokes only its own castling right.
- Capturing a rook on its home square revokes the opponent's right
  for that side.
- Castling legal: set up a position where all preconditions hold;
  `is_castling=True` move is accepted; both king and rook end up in
  the correct squares.
- Castling blocked by a piece between king and rook: rejected.
- Castling through check: set up an enemy piece attacking an
  intermediate square in the king's path *from a different slice*;
  castling is rejected even though the attacker is elsewhere (§3.9
  Def 10 clause 3, the "global attack" requirement).
- Castling out of check: rejected (clause 4).
- Castling into check: rejected (king's destination is attacked).
- Post-castling, both king's and rook's castling rights on that slice
  are gone from the set.
- Castling undo: push a castling move, pop it, board is bit-identical,
  castling rights restored, side-to-move restored.

Commit after 5A:
```
git add -A
git commit -m "Phase 5A: castling rights and castling moves (§3.9 Def 10)

GameState tracks castling_rights as frozenset[CastlingRight]; push
validates all six paper preconditions including the global-attack
constraint on the king's transit path. Rights are revoked by king
moves, rook moves, and rook captures on home squares.

Castling is a compound move: GameState.push/pop dispatches two
Board4D mutations but records a single logical move in its own
undo stack."
git push
```

## Sub-phase 5B — En passant

**Expected effort: moderate. Transient state + axis-parameterized.**

### En-passant scope (§3.10 Def 15)

En passant is defined independently for Y-oriented and W-oriented
pawns. The mechanics mirror 2D chess:

- A pawn makes a two-step move from its starting rank to rank 3
  (0-based rank 2 for white Y-pawn, rank 5 for black Y-pawn; similarly
  for W-pawns along the W axis).
- On the *immediately following* ply, an opposing pawn adjacent on
  the x-axis can capture it as if it had only advanced one square.
- The capturing pawn moves to the skipped square; the captured pawn is
  removed from its actual position (rank 3).
- Right to en-passant expires after that one ply.

**Axis restriction (§3.10 Def 15 final sentence):** mixed-direction en
passant (Y vs W) does not exist. A Y-pawn cannot capture a W-pawn en
passant, even if the geometry might otherwise allow it.

### State additions to GameState

```python
ep_target: Optional[Square4D]  # the skipped square, if any
ep_victim: Optional[Square4D]  # where the two-stepped pawn actually is
ep_axis: Optional[PawnAxis]    # Y or W; enforces no-mixed-direction
```

One two-stepping pawn sets all three together on its push; every
subsequent push clears them (unless the next push is *itself* another
two-step pawn, which sets them to new values).

### Move encoding

`Move4D.is_en_passant: bool` already exists. For an en-passant capture:
- `from_sq` is the capturing pawn's position.
- `to_sq` is the `ep_target` square.
- `is_en_passant = True` signals the capture mechanics.

The victim's square (different from `to_sq`) is recovered from
`ep_victim` at apply-time, so it doesn't need to be on the move.

### Validation

In `GameState.push`, when handling a pawn move:

1. If `move.is_en_passant`:
   - Verify `ep_target` is set and `move.to_sq == ep_target`.
   - Verify the capturing pawn's axis matches `ep_axis` (no mixed).
   - Verify the capturing pawn is adjacent to the ep_target on the
     x-axis (|Δx| = 1, other coords match the pre-step square).
   - Apply: remove the capturing pawn from from_sq, place it on
     to_sq, remove the victim from `ep_victim`.
2. Otherwise, detect if this move is a pawn two-step and set
   `ep_target / ep_victim / ep_axis` for the next ply.
3. If not a two-step, clear all three.

### Pseudo-legal generation

`pawn_moves` must also yield en-passant captures as candidates when
the GameState has an `ep_target`. But `pawn_moves` currently takes
`(origin, color, board)` — no game state. Two options:

A) **Pass GameState (or just ep state) through.** `pawn_moves(origin,
   color, board, ep_target=None, ep_axis=None)`. Pawn is already
   axis-parameterized and special-cased; this is more of the same.

B) **Emit en-passant from GameState, not pawn_moves.** `GameState.
   legal_moves` collects `pawn_moves` results and appends en-passant
   candidates separately when `ep_target` is set.

**Recommend B** — keeps `pawn_moves` concerned only with moves
intrinsic to the pawn's position, and `GameState` the sole owner of
transient position-dependent rules. Follow the same pattern castling
uses (validation in GameState, not in piece generators).

### Tests: `tests/test_en_passant.py`

- ep_target is None at `initial_position()`.
- Pawn two-step sets ep_target, ep_victim, ep_axis correctly for Y
  and W orientations, white and black (four combinations).
- ep_target clears after any next move that isn't itself a two-step.
- En-passant capture legal: set up a two-step; opposing same-axis
  pawn on adjacent x-file captures en passant; victim is removed
  from its actual rank-3 square.
- En-passant not available one ply later (if the two-stepping player
  makes any other move the following turn, the right expires).
- Mixed-axis en passant rejected: Y-pawn two-steps, W-pawn on adjacent
  x-file attempts en passant → rejected with clear error (§3.10 Def
  15 final sentence).
- En-passant undo: push en-passant, pop, the captured pawn is
  restored to its actual position (not the ep_target), capturing
  pawn is back on its pre-capture square, ep_target is restored.
- Multi-slice en passant: two-step occurs on (z=3, w=4); an
  adjacent-x-file pawn on the same slice can capture en passant; a
  pawn on a different slice at the same (x, y) cannot (en passant is
  slice-local).
- Capturing a pawn en passant revokes the victim's any-rook castling
  rights? No — pawns don't interact with castling rights. Test that
  castling rights are unchanged after en passant.

Commit after 5B:
```
git add -A
git commit -m "Phase 5B: en passant (§3.10 Def 15)

GameState tracks (ep_target, ep_victim, ep_axis) — set by pawn two-
steps, cleared on the following ply. The axis field enforces the
no-mixed-direction rule: a Y-pawn cannot en-passant capture a W-pawn.

En-passant candidates emitted by GameState.legal_moves, not
pawn_moves, keeping pseudo-legal generators concerned only with
intrinsic pawn geometry."
git push
```

## Sub-phase 5C — Halfmove clock + 50-move rule

**Expected effort: small. One counter, one draw predicate.**

### State additions

```python
halfmove_clock: int = 0
```

### Update rules

Standard chess (the paper inherits these):
- Increment `halfmove_clock` on every push.
- Reset to 0 on a pawn move (any pawn push, including captures and
  promotions).
- Reset to 0 on a capture (any move where `captured is not None`).

### Draw predicate

```python
def is_fifty_move_draw(self) -> bool:
    """True iff halfmove_clock >= 100 (50 full moves)."""
    return self.halfmove_clock >= 100
```

The 50-move rule is a draw *claim* in FIDE rules (a player can claim
it, not automatic), but the simpler interpretation is automatic at
the 75-move mark. For Phase 5, go with the claim-at-50 version
(predicate only; callers decide whether to honor it). Document the
choice.

### Tests: `tests/test_fifty_move.py`

- Halfmove clock starts at 0.
- Non-pawn non-capture move increments clock.
- Pawn move resets clock.
- Capture resets clock (test with a non-pawn capturing).
- Clock restored by pop after any of the above.
- `is_fifty_move_draw` returns True only at clock >= 100.

Commit after 5C:
```
git add -A
git commit -m "Phase 5C: halfmove clock and 50-move draw predicate

halfmove_clock increments on every push; resets on any pawn move or
any capture. is_fifty_move_draw() is a non-automatic predicate;
callers decide whether to honor it. FIDE's 'claim at 50' semantics,
not the automatic-at-75 variant."
git push
```

## Sub-phase 5D — Zobrist hashing + threefold repetition

**Expected effort: moderate. New hashing module plus history tracking.**

### New module: `src/chess4d/zobrist.py`

Zobrist-style position hashing (paper §4.7). Random bitstrings for
each `(square, piece)` combination, plus additional bitstrings for
side-to-move, each castling right, and each possible en-passant
target.

```python
# At module load:
_SEED = 0x4D_CHE55_20_26  # fixed seed for reproducible hashes
_PIECE_HASHES: dict[(Square4D, Color, PieceType, Optional[PawnAxis]), int]
_SIDE_HASH: int  # XOR when black to move
_CASTLING_HASHES: dict[CastlingRight, int]
_EP_HASHES: dict[Square4D, int]
```

(The pawn-axis wrinkle: two pawns on the same square of different
axes hash differently. This matters because promotion changes
placement in a way that should change the hash.)

### Hash function

```python
def hash_position(gs: GameState) -> int:
    """64-bit Zobrist hash of the game state.

    Two positions have the same hash iff:
    - All piece placements match (including pawn axis).
    - Side-to-move matches.
    - Castling rights set matches.
    - En-passant target matches.

    Does NOT include halfmove clock (irrelevant to position
    repetition).
    """
```

Implementation: XOR all the relevant component hashes.

**Performance note:** a naive "iterate every square" hash is O(4096).
An incremental hash maintained on push/pop is O(1) but adds
complexity. Phase 5 uses the naive version; Phase 6 incremental.

### State additions

```python
position_history: list[int]  # hashes of each position in this game
```

Populated by push (after state update, append the new hash); truncated
by pop. The full history is kept, not just a set — threefold
repetition counts exact occurrences.

### Draw predicate

```python
def is_threefold_repetition(self) -> bool:
    """True iff the current position hash has occurred 3+ times."""
    current = hash_position(self)
    return self.position_history.count(current) >= 3
```

Like 50-move, this is a claim predicate; callers decide.

### Tests: `tests/test_zobrist.py` + `tests/test_threefold.py`

Zobrist:
- Two independently-constructed `initial_position()` states hash
  equally.
- Moving and un-moving returns to the same hash.
- Different piece placements produce different hashes (sample 50
  random placements, verify all distinct hashes).
- Same placement with different side-to-move produces different
  hashes.
- Same placement with different castling rights produces different
  hashes.
- Pawn axis in hash: two placements identical except one square
  holds a Y-pawn vs a W-pawn should hash differently.

Threefold:
- Initial position: is_threefold_repetition is False.
- Position reached once: False.
- Position reached twice: False.
- Position reached three times: True.
- After the position is "left" (hash changes), it's no longer
  three-repeat even if it was before.
- Classic "shuffle kings back and forth" test: white king A1↔A2,
  black king A7↔A8, after six plies (three occurrences of the
  starting-cycle position) threefold triggers.

Commit after 5D:
```
git add -A
git commit -m "Phase 5D: Zobrist hashing and threefold repetition

New module chess4d.zobrist: fixed-seed Zobrist hashes over piece
placement, side-to-move, castling rights, en-passant target. Pawn
axis is part of the hash so promotion changes it correctly.

GameState tracks position_history: list[int]; is_threefold_repetition
is a claim predicate, not automatic.

Naive per-call hashing (O(pieces)); incremental hashing deferred to
Phase 6 performance work."
git push
```

## Sub-phase 5E — Integration + smoke

**Expected effort: small. Exercising all of Phase 5 together.**

### Smoke tests: `tests/test_phase5_smoke.py`

- **Full castling game:** set up a position where white can castle
  kingside on one slice; play: advance rook's path clearing pawns
  (3-4 plies), castle, verify rights revoked, push/pop round-trip
  preserves everything.

- **En passant + 50-move interaction:** play a sequence that
  includes a two-step, an en-passant capture (resets clock), then
  non-pawn-non-capture moves, verify clock increments correctly.

- **Repetition with castling rights:** reach a position twice via
  different move orders; if castling rights differ between the two
  paths (one side castled, the other didn't), the hashes differ and
  repetition does not count. Verify explicitly.

- **Initial position sanity:** call `initial_position()`,
  `legal_moves()` still returns candidates (performance is awful but
  correctness holds — see deferred work note below).

### Commit after 5E:
```
git add -A
git commit -m "Phase 5 smoke: castling + en passant + clocks + repetition

End-to-end smoke tests exercising Phase 5 features together. All
interactions behave correctly: rights revoke, clocks reset, hashes
distinguish states that differ only in game-history metadata."
git push
```

## After all five sub-phases

Final gates:
```
pytest -v            # expect ~380-420 tests
mypy --strict src/chess4d
ruff check src tests
git log --oneline -12
```

Sanity: `initial_position()` still returns a valid state; all Phase
4 behavior preserved; new features available via the public
`GameState` API.

## Request before starting 5A

Before implementing anything, show me:

1. **Castling-rights representation.** Which of the two options (per-
   rook `dict[(Color, Square4D), bool]` vs per-(color, slice, side)
   `frozenset[CastlingRight]`)? Justify briefly.

2. **En-passant emission strategy.** Option A (pass ep state into
   `pawn_moves`) or Option B (emit from `GameState.legal_moves`)? My
   recommendation was B; if you pick A, give a reason.

3. **GameState undo stack shape.** Phase 4's undo stack was
   essentially `Board4D._undo` (piece placement only). Phase 5 needs
   to undo castling rights, ep state, halfmove clock, and position
   history. Do you introduce a separate `GameState._undo` list of
   records, or do you embed these in Board4D's undo entries? My
   expectation: a separate `GameState._undo: list[_GameStateUndo]`
   that pairs 1:1 with `Board4D._undo` but carries the game-level
   deltas. Confirm or propose an alternative.

4. **Castling compound-move encoding.** Does `GameState.push` for
   a castling move call `Board4D.push` twice (king move, then rook
   move) and record two board undos, or once with a compound mutation
   that `Board4D` knows about? The two-push approach preserves
   `Board4D`'s pseudo-legal invariants; the compound approach is a
   new `Board4D` API. I lean toward two pushes with a single
   `GameState._undo` entry wrapping both. Confirm or propose.

5. **Zobrist seed.** Pick a fixed seed value and declare it in the
   module. It should be literally a constant, not computed; this
   ensures hashes are reproducible across runs and across the test
   suite. The paper doesn't specify; just pick one.

## Deferred work (tracked, not for this phase)

### Performance — `legal_moves` at 7.4s from initial position

Phase 4's `GameState.legal_moves()` on the 896-piece starting
position takes ~7.4 seconds wall-clock for its 2,356 candidates. The
dominant cost is the push-check-pop-per-candidate pattern combined
with the full attack scan per check. This is *correct* but unusable
for any search or gameplay integration.

Phase 5 does not address this. Phase 6 will: incremental attack
maps, incremental Zobrist hashing, and either bitboard-style or
VSA-style batched legality checks. Target: `legal_moves()` from the
initial position in under 200ms, ideally under 50ms.

The VSA/HDC approach from the chess-spectral work may genuinely
earn its place here (unlike in move generation, where we discussed
it doesn't). Attack-map construction is exactly the "query a lot of
attackers against a lot of targets" operation that binds/unbinds do
well, and the 896-piece density makes the fixed dimensional cost
amortize favorably.

### State tracking for alternative variants

`GameState` is currently Oana-Chiru-specific (the castling scope,
the en-passant axis restriction, the initial position). If future
work implements alternative 4D rulesets (Santoso, community variants,
the dimensional-consistent family from the spectral reflection),
some of this state model will need abstraction. Not in Phase 5.

### Connector to chess-spectral encoder

The library is now feature-complete enough to be useful to the
spectral encoder. The optional `[spectral]` extra hooks up later.

## Out of scope for Phase 5 (reminders)

- **Legal-move caching, attack-map caching, incremental hashing**
  — all Phase 6.
- **Game-termination orchestration** — `is_checkmate`, `is_stalemate`,
  `is_fifty_move_draw`, `is_threefold_repetition` are predicates.
  No `game_result: GameResult` enum consolidating them in this phase;
  callers compose the predicates themselves.
- **Resignation, draw offers, draw by insufficient material** — FIDE
  rules that require a player model. Skip.
- **Move notation (SAN-equivalent)** — still the coordinate-move
  notation from earlier phases. SAN-equivalent is a future phase.
- **FEN-equivalent serialization** — not yet; comes with the
  notation phase.