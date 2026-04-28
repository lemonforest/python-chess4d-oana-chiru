"""Reproduce the issue #7 F_D-plateau analysis under the corrected B1/B2 projectors.

Reads ``<run_dir>/spectralz/game_*.spectralz`` and emits the same three
tables the original issue #7 resolution comment carried.

Defaults to ``issue7_rerun/corpus_issue7_rerun_seed42`` (the seed=42
re-run); pass ``--run-dir <path>`` to point at a different corpus.
The retro-encoded apples-to-apples corpus
(``issue7_rerun/corpus_apples_to_apples``) and the seed=42 re-run can
both be analyzed by the same script with no other changes.

Outputs everything as markdown so it can drop straight into a GitHub
comment. Run with ``PYTHONIOENCODING=utf-8`` on Windows to avoid
console encoding errors on the ≥ symbol; redirect stdout to a file
to bypass that entirely.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

import numpy as np

from chess_spectral.frame_4d import read_spectralz_v4

# Channel layout from chess_spectral.encoder_4d.CHANNELS_4D — 11 channels,
# each 4096-dim, totaling 45 056. FD_DIAG is the last channel.
CHANNEL_DIM = 4096
FD_OFFSET = 10 * CHANNEL_DIM  # 40960
FD_END = 11 * CHANNEL_DIM     # 45056


def load_corpus(run_dir: Path) -> tuple[dict, list[np.ndarray]]:
    """Load manifest + per-game encoding stack ``(n_frames, 45056)``."""
    manifest = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    games: list[np.ndarray] = []
    for row in manifest["games"]:
        sz_path = run_dir / row["spectralz"]
        _, frames = read_spectralz_v4(sz_path)
        stack = np.stack([f.encoding for f in frames], axis=0)
        games.append(stack)
    return manifest, games


def fd_energy(enc: np.ndarray) -> float:
    """Squared L2 norm of the FD_DIAG channel — matches channel_energies_4d."""
    s = enc[FD_OFFSET:FD_END]
    return float(np.dot(s.astype(np.float64), s.astype(np.float64)))


def longest_constant_run(values: list[int]) -> tuple[int, int, int]:
    """Return (length, onset_index, plateau_value) of the longest constant run."""
    best_len = 1
    best_onset = 0
    best_val = values[0]
    cur_len = 1
    cur_onset = 0
    for i in range(1, len(values)):
        if values[i] == values[i - 1]:
            cur_len += 1
        else:
            cur_len = 1
            cur_onset = i
        if cur_len > best_len:
            best_len = cur_len
            best_onset = cur_onset
            best_val = values[i]
    return best_len, best_onset, best_val


def fd_plateau_table(games: list[np.ndarray], pivot_ply: int) -> list[list[str]]:
    rows = []
    for i, g in enumerate(games, start=1):
        # Use bytes of the FD slice to detect bit-identical runs (defensive
        # against float NaN equality quirks; we want byte-level identity).
        keys = [g[k, FD_OFFSET:FD_END].tobytes() for k in range(g.shape[0])]
        # Index plateau by run-length of consecutive equal keys.
        best_len = 1
        best_onset = 0
        cur_len = 1
        cur_onset = 0
        for k in range(1, len(keys)):
            if keys[k] == keys[k - 1]:
                cur_len += 1
            else:
                cur_len = 1
                cur_onset = k
            if cur_len > best_len:
                best_len = cur_len
                best_onset = cur_onset
        # Plateau value: squared L2 norm of FD_DIAG at the onset frame.
        plateau_val = fd_energy(g[best_onset])
        # F_D scalar trajectory (squared L2 per frame).
        fd_scalars = [fd_energy(g[k]) for k in range(g.shape[0])]
        rows.append([
            f"g{i}",
            f"{best_len} / {g.shape[0]}",
            f"{plateau_val:,.0f}",
            f"{best_onset}",
            f"{pivot_ply + best_onset}",
            f"{min(fd_scalars):,.0f}",
            f"{max(fd_scalars):,.0f}",
        ])
    return rows


def consecutive_bit_identity(games: list[np.ndarray]) -> list[list[str]]:
    rows = []
    total_whole = 0
    total_fd_only = 0
    total_both_differ = 0
    total_pairs = 0
    for i, g in enumerate(games, start=1):
        whole_match = 0
        fd_only_match = 0
        both_differ = 0
        for k in range(1, g.shape[0]):
            a = g[k - 1]
            b = g[k]
            whole_id = (a.tobytes() == b.tobytes())
            fd_id = (a[FD_OFFSET:FD_END].tobytes() == b[FD_OFFSET:FD_END].tobytes())
            if whole_id:
                whole_match += 1
            elif fd_id:
                fd_only_match += 1
            else:
                both_differ += 1
        rows.append([f"g{i}", str(whole_match), str(fd_only_match), str(both_differ)])
        total_whole += whole_match
        total_fd_only += fd_only_match
        total_both_differ += both_differ
        total_pairs += whole_match + fd_only_match + both_differ
    rows.append([
        "**total**",
        f"**{total_whole}**",
        f"**{total_fd_only}** ({100 * total_fd_only / total_pairs:.1f}%)",
        f"**{total_both_differ}**",
    ])
    return rows


def fd_cosine_consecutive(games: list[np.ndarray]) -> list[list[str]]:
    rows = []
    for i, g in enumerate(games, start=1):
        cosines = []
        for k in range(1, g.shape[0]):
            a = g[k - 1, FD_OFFSET:FD_END].astype(np.float64)
            b = g[k, FD_OFFSET:FD_END].astype(np.float64)
            na = float(np.linalg.norm(a))
            nb = float(np.linalg.norm(b))
            if na == 0.0 or nb == 0.0:
                cosines.append(float("nan"))
            else:
                cosines.append(float(np.dot(a, b) / (na * nb)))
        finite = [c for c in cosines if not math.isnan(c)]
        if finite:
            mn = min(finite)
            mx = max(finite)
            high = sum(1 for c in finite if c >= 0.99999999)
        else:
            mn = mx = float("nan")
            high = 0
        rows.append([
            f"g{i}",
            f"{mn:.10f}",
            f"{mx:.10f}",
            f"{high} / {len(cosines)}",
        ])
    return rows


def cross_game_cosine_last_frame(games: list[np.ndarray]) -> list[list[str]]:
    last = np.stack([g[-1] for g in games])  # (6, 45056)
    norms = np.linalg.norm(last, axis=1)
    n = len(games)
    rows = []
    for i in range(n):
        row = [f"g{i + 1}"]
        for j in range(n):
            if norms[i] == 0 or norms[j] == 0:
                row.append("nan")
            else:
                cos = float(np.dot(last[i], last[j]) / (norms[i] * norms[j]))
                row.append(f"{cos:+.4f}")
        rows.append(row)
    return rows


def render_md_table(headers: list[str], rows: list[list[str]]) -> str:
    sep = "|".join("---" for _ in headers)
    out = ["| " + " | ".join(headers) + " |", "| " + sep + " |"]
    for r in rows:
        out.append("| " + " | ".join(r) + " |")
    return "\n".join(out)


def main() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--run-dir",
        type=Path,
        default=repo_root / "issue7_rerun" / "corpus_issue7_rerun_seed42",
        help="Path to a chess4d corpus run_dir (containing manifest.json + "
        "spectralz/). Defaults to the seed=42 re-run.",
    )
    args = parser.parse_args()
    run_dir = args.run_dir
    manifest, games = load_corpus(run_dir)
    pivot_ply = manifest["games"][0]["pivot_ply"]
    n_frames = games[0].shape[0]
    tv = manifest["tool_versions"]
    print(
        f"# Issue #7 re-run — chess4d {tv.get('chess4d', '?')} / "
        f"chess-spectral {tv.get('chess_spectral', '?')}\n"
    )
    print(f"Source corpus: `{manifest['run_id']}`")
    print(f"Generated: {manifest['generated_utc']}")
    print(f"Tool versions: {manifest['tool_versions']}")
    print(f"Aggregates: {manifest['aggregates']}")
    print(f"Encoded plies per game: {n_frames} (pivot ply {pivot_ply})")
    print()

    print("## Task 2 — F_D plateau summary (longest bit-exact run per game)\n")
    rows = fd_plateau_table(games, pivot_ply)
    print(render_md_table(
        ["Game", "Plateau length", "Plateau value", "Onset frame", "Onset ply",
         "F_D min", "F_D max"],
        rows,
    ))
    print()

    print("## Task 3 — Consecutive-frame bit-identity (40 pairs per game)\n")
    rows = consecutive_bit_identity(games)
    print(render_md_table(
        ["Game", "Whole vector bit-identical",
         "F_D-only bit-identical (rest differs)", "Both differ"],
        rows,
    ))
    print()

    print("## F_D consecutive-frame cosine similarity (4096-dim slice)\n")
    rows = fd_cosine_consecutive(games)
    print(render_md_table(
        ["Game", "min consecutive cos", "max consecutive cos",
         "pairs >= 0.99999999 / 40"],
        rows,
    ))
    print()

    print("## Cross-game cosine at last frame (full 45,056-dim vector)\n")
    rows = cross_game_cosine_last_frame(games)
    print(render_md_table(
        ["", *[f"g{i + 1}" for i in range(len(games))]],
        rows,
    ))
    print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
