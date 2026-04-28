# Issue #7 re-run under chess-spectral 1.2.3 / chess4d 0.3.3

Source corpus: `corpus_issue7_rerun_seed42`
Generated: 2026-04-25T20:42:35.411651+00:00
Tool versions: {'python': '3.12.10', 'chess4d': '0.3.3', 'chess_spectral': '1.2.3'}
Aggregates: {'n_games': 6, 'n_encoded_games': 6, 'total_plies': 1404, 'total_encoded_plies': 240, 'n_errors': 0, 'wall_time_s': 1419.078}
Encoded plies per game: 41 (pivot ply 194)

## Task 2 — F_D plateau summary (longest bit-exact run per game)

| Game | Plateau length | Plateau value | Onset frame | Onset ply | F_D min | F_D max |
| ---|---|---|---|---|---|--- |
| g1 | 26 / 41 | 1,091,601,304 | 15 | 209 | 91,072,241 | 1,091,601,304 |
| g2 | 37 / 41 | 26,972,072 | 4 | 198 | 26,972,072 | 2,266,857,516 |
| g3 | 41 / 41 | 3,935,028,254 | 0 | 194 | 3,935,028,254 | 3,935,028,254 |
| g4 | 22 / 41 | 26,972,072 | 0 | 194 | 23,142,312 | 26,972,072 |
| g5 | 3 / 41 | 0 | 0 | 194 | 0 | 0 |
| g6 | 4 / 41 | 179,456 | 37 | 231 | 0 | 179,456 |

## Task 3 — Consecutive-frame bit-identity (40 pairs per game)

| Game | Whole vector bit-identical | F_D-only bit-identical (rest differs) | Both differ |
| ---|---|---|--- |
| g1 | 0 | 39 | 1 |
| g2 | 0 | 39 | 1 |
| g3 | 0 | 40 | 0 |
| g4 | 0 | 38 | 2 |
| g5 | 0 | 10 | 30 |
| g6 | 0 | 9 | 31 |
| **total** | **0** | **175** (72.9%) | **65** |

## F_D consecutive-frame cosine similarity (4096-dim slice)

| Game | min consecutive cos | max consecutive cos | pairs >= 0.99999999 / 40 |
| ---|---|---|--- |
| g1 | -0.9924636231 | 1.0000000000 | 39 / 40 |
| g2 | 0.9813348980 | 1.0000000000 | 39 / 40 |
| g3 | 1.0000000000 | 1.0000000000 | 40 / 40 |
| g4 | 0.9993414588 | 1.0000000000 | 38 / 40 |
| g5 | 0.3093650529 | 1.0000000000 | 10 / 40 |
| g6 | -0.0116286321 | 1.0000000000 | 9 / 40 |

## Cross-game cosine at last frame (full 45,056-dim vector)

|  | g1 | g2 | g3 | g4 | g5 | g6 |
| ---|---|---|---|---|---|--- |
| g1 | +1.0000 | +0.9271 | -0.9950 | -0.8971 | +0.0504 | -0.1363 |
| g2 | +0.9271 | +1.0000 | -0.9027 | -0.7663 | +0.3247 | +0.1524 |
| g3 | -0.9950 | -0.9027 | +1.0000 | +0.9271 | +0.0276 | +0.2126 |
| g4 | -0.8971 | -0.7663 | +0.9271 | +1.0000 | +0.3125 | +0.4778 |
| g5 | +0.0504 | +0.3247 | +0.0276 | +0.3125 | +1.0000 | +0.8973 |
| g6 | -0.1363 | +0.1524 | +0.2126 | +0.4778 | +0.8973 | +1.0000 |

