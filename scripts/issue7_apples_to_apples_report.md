# Issue #7 re-run under chess-spectral 1.2.3 / chess4d 0.3.3

Source corpus: `corpus_20260420_025419_unseeded`
Generated: 2026-04-27T03:53:31.732114+00:00
Tool versions: {'python': '3.12.10', 'chess4d': '0.3.3', 'chess_spectral': '1.2.3'}
Aggregates: {'n_games': 6, 'n_encoded_games': 6, 'total_plies': 1404, 'total_encoded_plies': 240, 'n_errors': 0, 'wall_time_s': 1290.062}
Encoded plies per game: 41 (pivot ply 194)

## Task 2 — F_D plateau summary (longest bit-exact run per game)

| Game | Plateau length | Plateau value | Onset frame | Onset ply | F_D min | F_D max |
| ---|---|---|---|---|---|--- |
| g1 | 35 / 41 | 717,824 | 6 | 200 | 179,456 | 717,824 |
| g2 | 41 / 41 | 1,876,203,920 | 0 | 194 | 1,876,203,920 | 1,876,203,920 |
| g3 | 33 / 41 | 265,054,961 | 8 | 202 | 265,054,961 | 3,456,649,573 |
| g4 | 27 / 41 | 1,842,183,826 | 0 | 194 | 1,117,900,953 | 1,842,183,826 |
| g5 | 33 / 41 | 2,666,924,649 | 8 | 202 | 2,666,924,649 | 2,707,588,448 |
| g6 | 27 / 41 | 1,808,522,628 | 0 | 194 | 1,808,522,628 | 7,234,090,511 |

## Task 3 — Consecutive-frame bit-identity (40 pairs per game)

| Game | Whole vector bit-identical | F_D-only bit-identical (rest differs) | Both differ |
| ---|---|---|--- |
| g1 | 0 | 39 | 1 |
| g2 | 0 | 40 | 0 |
| g3 | 0 | 39 | 1 |
| g4 | 0 | 39 | 1 |
| g5 | 0 | 39 | 1 |
| g6 | 0 | 39 | 1 |
| **total** | **0** | **235** (97.9%) | **5** |

## F_D consecutive-frame cosine similarity (4096-dim slice)

| Game | min consecutive cos | max consecutive cos | pairs >= 0.99999999 / 40 |
| ---|---|---|--- |
| g1 | 1.0000000000 | 1.0000000000 | 40 / 40 |
| g2 | 1.0000000000 | 1.0000000000 | 40 / 40 |
| g3 | 0.9993799253 | 1.0000000000 | 39 / 40 |
| g4 | 0.9996185453 | 1.0000000000 | 39 / 40 |
| g5 | 0.9999952326 | 1.0000000000 | 39 / 40 |
| g6 | 1.0000000000 | 1.0000000000 | 40 / 40 |

## Cross-game cosine at last frame (full 45,056-dim vector)

|  | g1 | g2 | g3 | g4 | g5 | g6 |
| ---|---|---|---|---|---|--- |
| g1 | +1.0000 | -0.3363 | +0.4667 | -0.3271 | -0.3378 | +0.3921 |
| g2 | -0.3363 | +1.0000 | -0.9844 | +0.9993 | +0.9995 | -0.9977 |
| g3 | +0.4667 | -0.9844 | +1.0000 | -0.9824 | -0.9855 | +0.9932 |
| g4 | -0.3271 | +0.9993 | -0.9824 | +1.0000 | +0.9985 | -0.9964 |
| g5 | -0.3378 | +0.9995 | -0.9855 | +0.9985 | +1.0000 | -0.9979 |
| g6 | +0.3921 | -0.9977 | +0.9932 | -0.9964 | -0.9979 | +1.0000 |

