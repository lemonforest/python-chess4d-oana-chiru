# Local chess-spectral binaries (gitignored)

Drop compiled `chess-spectral` binaries here for parity testing and
(eventually) faster corpus regeneration. The whole directory is
`.gitignore`d — each developer brings their own platform build.

## Current binary state (chess-spectral v1.1.1)

```
spectral_4d.exe   4D encoder, C17
spectral.exe      2D encoder, C17
cs_test.exe       internal C test runner
*.lib             static libs (cs_core, cs_core_4d, miniz)
```

### What's working today

`spectral_4d.exe` exposes:

```
spectral_4d version
spectral_4d encode-fixture --positions-jsonl <path> --name <fixture>
```

`encode-fixture` reads a named position from a JSONL fixture file and
writes 45 056 little-endian float32 values (180 224 bytes) to stdout.
This is the **C ⇄ Python parity-test entry point** — useful for
verifying that both encoders agree on a given position bit-exactly.

### What's stubbed (phase 5 upstream)

```
spectral_4d encode      NDJSON4 → .spectralz4 bulk encoding   [P5]
spectral_4d encode-fen4 single-FEN encode                     [P5]
spectral_4d csv         per-ply channel energies              [P5]
```

Until those land, **bulk corpus regeneration must use the Python
encoder** (`chess-spectral` ≥ 1.2.3 via the `[spectral]` extra). The C
binaries can still drive parity tests against the Python reference.

## Channel layout (printed by `spectral_4d --help`)

11 channels × 4096 board eigenmodes = 45 056 floats per position:

| Ch  | Name                                         | Dim range      |
|-----|----------------------------------------------|----------------|
| 0   | A_1 orbit-mean                               | 0..4095        |
| 1-4 | std-4D coord residuals                       | 4096..20479    |
| 5-7 | symmetric 3D cross-piece fiber               | 20480..32767   |
| 8   | antisymmetric pawn fiber, W-axis             | 32768..36863   |
| 9   | antisymmetric pawn fiber, Y-axis (NEW v1.1.1)| 36864..40959   |
| 10  | diagonal deviation (rook shadow) — **F_D**   | 40960..45055   |

This is the layout `scripts/analyze_issue7_rerun.py` slices against to
isolate the F_D channel.

## When phase-5 bulk encode lands

Once `spectral_4d encode` is implemented, we can wire up a corpus-gen
script that takes `--encoder-bin scripts/binaries/spectral_4d.exe` and
shells out to the binary instead of calling Python `encode_4d`. That
should drop the issue #7 re-run from ~20 minutes to seconds.
