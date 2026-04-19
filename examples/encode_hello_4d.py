"""Smoke example for the chess4d ⇄ chess-spectral adapter.

Plays five random moves from the Oana-Chiru starting position, writes a
``spectralz`` v4 file to ``hello.spectralz`` in the current directory,
reads it back, and prints a one-line summary.

Run::

    python examples/encode_hello_4d.py
"""

from __future__ import annotations

import random
from pathlib import Path

from chess4d import initial_position
from chess4d.spectral import write_spectralz
from chess_spectral.frame_4d import read_spectralz_v4


def main() -> None:
    rng = random.Random(0)
    gs = initial_position()
    moves = []
    for _ in range(5):
        legal = list(gs.legal_moves())
        if not legal:
            break
        move = rng.choice(legal)
        gs.push(move)
        moves.append(move)

    out = Path("hello.spectralz")
    nbytes = write_spectralz(out, initial_position(), moves)
    header, frames = read_spectralz_v4(out)

    print(
        f"wrote {out} ({nbytes} bytes): version={header.version} "
        f"encoding_dim={header.encoding_dim} n_plies={header.n_plies} "
        f"frames_read={len(frames)}"
    )


if __name__ == "__main__":
    main()
