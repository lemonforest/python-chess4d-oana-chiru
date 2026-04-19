"""Random-playout corpus generation (Phase 8).

Produces spectralz v4 files from random legal playouts off the
Oana-Chiru starting position. Used for downstream empirical work —
measuring F_D fingerprints, verifying spectral predictions against
engine data, building tiny training sets.

Entry points::

    chess4d.corpus.generate_corpus(n_games=N, seed=S, ...) -> list[Path]

and, via ``[project.scripts]``::

    chess4d-corpus-gen --n-games 10 --seed 42 --output ./corpus

The CLI also runs via ``python -m chess4d.corpus``. Termination
reasons ("checkmate" / "stalemate" / "max_plies") are logged to stderr
and returned in the per-game summary so the caller can tally them.
"""

from __future__ import annotations

import argparse
import random
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from chess4d.spectral import write_spectralz
from chess4d.startpos import initial_position
from chess4d.types import Move4D


__all__ = ["GameSummary", "generate_corpus", "main", "play_random_game"]


@dataclass(frozen=True)
class GameSummary:
    """One row of per-game stats from :func:`generate_corpus`.

    ``termination`` is one of ``"checkmate"``, ``"stalemate"``, or
    ``"max_plies"``. ``bytes_written`` is the spectralz file size
    reported by :func:`write_spectralz`.
    """

    path: Path
    plies: int
    termination: str
    bytes_written: int


def play_random_game(
    rng: random.Random, max_plies: int
) -> tuple[list[Move4D], str]:
    """Play a uniformly-random legal game and return ``(moves, termination)``.

    Stops at checkmate, stalemate, or ``max_plies``. The engine's
    full legality pipeline (§3.4 Def 3) is honored on every ply via
    :meth:`GameState.legal_moves`, so the resulting move list is
    always a valid Oana-Chiru game prefix.
    """
    gs = initial_position()
    moves: list[Move4D] = []
    for _ in range(max_plies):
        legal = list(gs.legal_moves())
        if not legal:
            return moves, "checkmate" if gs.in_check() else "stalemate"
        move = rng.choice(legal)
        gs.push(move)
        moves.append(move)
    return moves, "max_plies"


def generate_corpus(
    n_games: int,
    *,
    max_plies: int = 200,
    seed: Optional[int] = None,
    output_dir: str | Path = "./corpus",
) -> list[GameSummary]:
    """Generate ``n_games`` random-playout spectralz v4 files.

    ``seed`` fully determines the output: two calls with the same
    ``(n_games, max_plies, seed)`` write byte-identical files. Files
    are named ``game_001.spectralz`` through ``game_{n_games:03d}
    .spectralz``; the output directory is created if absent.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    summaries: list[GameSummary] = []
    for i in range(1, n_games + 1):
        moves, termination = play_random_game(rng, max_plies)
        path = out / f"game_{i:03d}.spectralz"
        start = initial_position()
        nbytes = write_spectralz(path, start, moves)
        summaries.append(
            GameSummary(
                path=path,
                plies=len(moves),
                termination=termination,
                bytes_written=nbytes,
            )
        )
        print(
            f"game_{i:03d}: plies={len(moves):4d} "
            f"term={termination:10s} bytes={nbytes}",
            file=sys.stderr,
        )
    return summaries


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="chess4d-corpus-gen",
        description="Generate a corpus of spectralz v4 files from random "
        "Oana-Chiru playouts.",
    )
    parser.add_argument(
        "--n-games", type=int, default=10, help="Number of games to generate."
    )
    parser.add_argument(
        "--max-plies",
        type=int,
        default=200,
        help="Cap on plies per game before forcing termination.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility (omit for nondeterministic).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("./corpus"),
        help="Directory to write game_NNN.spectralz files into.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point. Returns the process exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    summaries = generate_corpus(
        n_games=args.n_games,
        max_plies=args.max_plies,
        seed=args.seed,
        output_dir=args.output,
    )
    total_bytes = sum(s.bytes_written for s in summaries)
    total_plies = sum(s.plies for s in summaries)
    print(
        f"wrote {len(summaries)} games, {total_plies} plies, "
        f"{total_bytes} bytes to {args.output}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
