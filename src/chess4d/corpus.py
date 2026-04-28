"""Random-playout corpus generation (Phase 8).

Produces a corpus directory that mirrors the ``chess-maths-the-movie``
layout, so chess4d corpora drop into the same tooling as the 2D chess
spectral viewer. Each run lands under a dated ``run_id`` subdirectory::

    <output>/<run_id>/
      manifest.json                    # run metadata + per-game rows
      c4d/game_NNN.c4d                 # compact 4D move notation
      ndjson/game_NNN.ndjson           # per-ply pos4 snapshots + moves
      spectralz/game_NNN.spectralz     # 45 056-dim per-ply encoding

The ``spectralz/`` directory is absent with ``--no-encode`` and holds
tail-only frames under ``--encode-last N`` (frames carry absolute ply
numbers so they line up with the NDJSON and sidecar c4d).

Two-pass generation
-------------------
Corpus generation is a two-pass operation, with NDJSON as the bridge:

1. **Playout pass** — always: :func:`generate_corpus` plays each game
   to completion, writes ``c4d/game_NNN.c4d`` and
   ``ndjson/game_NNN.ndjson``. Early terminations (checkmate /
   stalemate) are captured in the NDJSON ``game_header.termination``
   field before the final ply count is known.
2. **Encoding pass** — optional: :func:`encode_ndjson_to_spectralz`
   reads the NDJSON back, slices the final ``--encode-last N`` plies
   if requested, and writes a spectralz v4 file with absolute ply
   numbers. ``--encode-last`` is therefore an encoder-time decision,
   not a playout-time one — the full move list is already on disk.

Because the encoding pass runs off the NDJSON and nothing else, you
can retro-encode an existing ``--no-encode`` corpus via
:func:`encode_existing_run` or the ``chess4d-corpus-encode`` CLI
without replaying the games.

Entry points::

    chess4d.corpus.generate_corpus(n_games=N, seed=S, ...) -> CorpusResult
    chess4d.corpus.encode_existing_run(run_dir, *, last_n=...) -> CorpusResult
    chess4d.corpus.encode_ndjson_to_spectralz(ndjson, sz, *, last_n=...)
    chess4d.corpus.read_ndjson_game(path) -> (GameState, list[Move4D], dict)

and, via ``[project.scripts]``::

    chess4d-corpus-gen --n-games 10 --seed 42 --output ./corpus
    chess4d-corpus-gen --n-games 1 --max-plies 500 --encode-last 30
    chess4d-corpus-gen --n-games 1 --max-plies 500 --no-encode
    chess4d-corpus-gen --n-games 1 --run-id fixed-corpus-v1
    chess4d-corpus-encode ./corpus/<run_id>
    chess4d-corpus-encode ./corpus/<run_id> --last-n 30

The CLIs also run via ``python -m chess4d.corpus``. Termination
reasons ("checkmate" / "stalemate" / "max_plies") are logged to stderr
and carried on each :class:`GameSummary` so the caller can tally them.

Schema docs
-----------
* NDJSON schema id: ``"chess4d-ndjson-v1"`` on line 1.
* Manifest top-level keys: ``generated_utc``, ``run_id``, ``source``,
  ``fetch_params``, ``tool_versions``, ``aggregates``, ``games``.
* Per-ply pos4 dict uses the v1.1.1 Oana-Chiru schema — 2-char pawn
  values (``Pw``/``Py``/``pw``/``py``) and 1-char non-pawns.

The ``[spectral]`` extra is only required when encoding is enabled;
``chess_spectral`` is imported lazily inside
:func:`encode_ndjson_to_spectralz` so the playout pass (and any
NDJSON-only tooling) runs on a bare install.
"""

from __future__ import annotations

import argparse
import copy
import json
import random
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from chess4d.notation import write_game_file
from chess4d.startpos import initial_position
from chess4d.state import GameState
from chess4d.types import Color, Move4D, PawnAxis, PieceType, Square4D


__all__ = [
    "CorpusResult",
    "GameSummary",
    "encode_existing_run",
    "encode_ndjson_to_spectralz",
    "encode_main",
    "generate_corpus",
    "main",
    "play_random_game",
    "read_ndjson_game",
    "write_ndjson_game",
]


NDJSON_FORMAT_ID = "chess4d-ndjson-v1"


@dataclass(frozen=True)
class GameSummary:
    """One row of per-game stats from :func:`generate_corpus`.

    * ``stem`` — filename stem shared by the c4d / ndjson / spectralz
      artifacts (e.g. ``"game_001"``).
    * ``c4d_path`` — path to the compact 4D move log (always present).
    * ``ndjson_path`` — path to the NDJSON per-ply record stream
      (always present).
    * ``encoding_path`` — path to the spectralz file, or ``None`` when
      encoding was skipped via ``encode=False``.
    * ``plies`` — total plies played (length of the c4d/NDJSON move list).
    * ``encoded_plies`` — plies carried in the spectralz file; equal
      to ``plies`` by default, ``min(plies, encode_last)`` when a tail
      is requested, and ``0`` when encoding was skipped.
    * ``pivot_ply`` — absolute ply of the first encoded frame, i.e.
      ``max(0, plies - encode_last)``. Zero when encoding the full game
      or when encoding was skipped.
    * ``termination`` — one of ``"checkmate"``, ``"stalemate"``,
      ``"max_plies"``.
    * ``c4d_bytes`` / ``ndjson_bytes`` / ``encoding_bytes`` — on-disk
      sizes; ``encoding_bytes`` is ``0`` when encoding was skipped.
    """

    stem: str
    c4d_path: Path
    ndjson_path: Path
    encoding_path: Optional[Path]
    plies: int
    encoded_plies: int
    pivot_ply: int
    termination: str
    c4d_bytes: int
    ndjson_bytes: int
    encoding_bytes: int


@dataclass(frozen=True)
class CorpusResult:
    """Top-level return value of :func:`generate_corpus`.

    * ``run_dir`` — the ``<output>/<run_id>/`` directory holding all
      artifacts for this run.
    * ``run_id`` — the subdirectory basename (either caller-provided or
      auto-generated via :func:`_auto_run_id`).
    * ``manifest_path`` — path to the run's ``manifest.json``.
    * ``games`` — one :class:`GameSummary` per generated game, in the
      order they were played.
    """

    run_dir: Path
    run_id: str
    manifest_path: Path
    games: list[GameSummary]


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


# --- pos4 / NDJSON ----------------------------------------------------------


_NONPAWN_CHAR: dict[PieceType, str] = {
    PieceType.KNIGHT: "N",
    PieceType.BISHOP: "B",
    PieceType.ROOK: "R",
    PieceType.QUEEN: "Q",
    PieceType.KING: "K",
}


def _linear_index(sq: Square4D) -> int:
    """Encoder's linear square index: ``(x<<9) | (y<<6) | (z<<3) | w``.

    Matches :func:`chess4d.spectral._linear_index` bit-for-bit so the
    NDJSON pos4 dict and the spectralz channel layout share one
    addressing scheme.
    """
    return (sq.x << 9) | (sq.y << 6) | (sq.z << 3) | sq.w


def _pos4_compact(gs: GameState) -> dict[str, str]:
    """Serialize the occupied board into a JSON-safe pos4 dict.

    Keys are the linear square index (``str(int)``), values follow the
    v1.1.1 Oana-Chiru schema:

    * Pawns are two characters — ``P``/``p`` (white/black) followed by
      ``y``/``w`` (forward axis).
    * Non-pawns are one character — ``K``/``Q``/``R``/``B``/``N``
      uppercase for White and lowercase for Black.

    Empty squares are omitted, matching the 4D "FEN-equivalent" format
    described in the ``chess_spectral_4d_notebook`` spec. JSON object
    keys must be strings, so the integer linear index is emitted as a
    decimal string; re-indexing on the reader side is a single
    ``int(k)``.
    """
    pos4: dict[str, str] = {}
    for color in (Color.WHITE, Color.BLACK):
        uppercase = color is Color.WHITE
        for sq, piece in gs.board.pieces_of(color):
            key = str(_linear_index(sq))
            if piece.piece_type is PieceType.PAWN:
                axis = piece.pawn_axis
                if axis is None:  # pragma: no cover — Piece invariant
                    raise ValueError(
                        f"Pawn at {sq} has no pawn_axis; cannot encode."
                    )
                color_char = "P" if uppercase else "p"
                axis_char = "y" if axis is PawnAxis.Y else "w"
                pos4[key] = f"{color_char}{axis_char}"
                continue
            base = _NONPAWN_CHAR.get(piece.piece_type)
            if base is None:  # pragma: no cover — PieceType closed set
                raise ValueError(
                    f"Unrecognized piece_type {piece.piece_type!r} at {sq}."
                )
            pos4[key] = base if uppercase else base.lower()
    return pos4


def _move_record(
    move: Optional[Move4D],
) -> dict[str, Any]:
    """Fields describing the move that produced this position.

    The ply-0 record carries ``move_from = move_to = None`` and
    ``is_castling = is_en_passant = False``; subsequent records carry
    the 4-tuple coordinates and the promotion piece-type name (or
    ``None`` if not a promotion).
    """
    if move is None:
        return {
            "move_from": None,
            "move_to": None,
            "move_promo": None,
            "is_castling": False,
            "is_en_passant": False,
        }
    return {
        "move_from": [move.from_sq.x, move.from_sq.y, move.from_sq.z, move.from_sq.w],
        "move_to": [move.to_sq.x, move.to_sq.y, move.to_sq.z, move.to_sq.w],
        "move_promo": move.promotion.name if move.promotion is not None else None,
        "is_castling": bool(move.is_castling),
        "is_en_passant": bool(move.is_en_passant),
    }


def write_ndjson_game(
    path: Path,
    start: GameState,
    moves: list[Move4D],
    *,
    termination: str,
    game_index: int,
    seed: Optional[int],
) -> int:
    """Write one game as NDJSON; return bytes written.

    File shape::

        line 1   format header          {"format":"chess4d-ndjson-v1"}
        line 2   game header            {"type":"game_header", ...}
        line 3+  per-ply record         one per position (ply 0 .. n_plies)

    The initial position is included as ply 0 with no move fields, so
    an N-move game yields N+2 lines total (header + game header + N+1
    records). ``side_to_move`` is the color that moves *next* from this
    position — flipped each ply by :meth:`GameState.push`.
    """
    current = copy.deepcopy(start)
    lines: list[str] = []
    lines.append(json.dumps({"format": NDJSON_FORMAT_ID}, sort_keys=True))
    headers: dict[str, Any] = {
        "termination": termination,
        "n_plies": len(moves),
    }
    if seed is not None:
        headers["seed"] = seed
    lines.append(
        json.dumps(
            {"type": "game_header", "game": game_index, "headers": headers},
            sort_keys=True,
        )
    )
    # Ply 0 — initial position, no move.
    record_0: dict[str, Any] = {
        "game": game_index,
        "ply": 0,
        **_move_record(None),
        "side_to_move": current.side_to_move.name,
        "pos4": _pos4_compact(current),
    }
    lines.append(json.dumps(record_0, sort_keys=True))
    for ply, move in enumerate(moves, start=1):
        current.push(move)
        record: dict[str, Any] = {
            "game": game_index,
            "ply": ply,
            **_move_record(move),
            "side_to_move": current.side_to_move.name,
            "pos4": _pos4_compact(current),
        }
        lines.append(json.dumps(record, sort_keys=True))
    text = "\n".join(lines) + "\n"
    path.write_text(text, encoding="utf-8")
    # Report the on-disk size (which may differ from ``len(text)`` on
    # Windows when newline translation rewrites ``\n`` to ``\r\n``).
    return path.stat().st_size


def read_ndjson_game(
    path: str | Path,
) -> tuple[GameState, list[Move4D], dict[str, Any]]:
    """Parse a ``chess4d-ndjson-v1`` file; return ``(start, moves, headers)``.

    The inverse of :func:`write_ndjson_game`. Assumes the file was
    written from the standard Oana-Chiru :func:`initial_position` — the
    ply-0 ``pos4`` snapshot is validated against that starting
    configuration, and a ``ValueError`` is raised if it doesn't match
    (so a file written from a mid-game snapshot by some future producer
    won't silently produce a wrong encoding).

    This is the adapter the :func:`encode_ndjson_to_spectralz`
    retro-encoder drives off of: NDJSON is the shared bridge between
    the playout pass (c4d + NDJSON + manifest) and the optional
    encoding pass (spectralz). It is *not* required for the encoder
    to run — the in-memory ``(GameState, moves)`` form still works
    directly via :func:`chess4d.spectral.write_spectralz`.

    Returns
    -------
    start
        The canonical :func:`initial_position` (a fresh deep copy, so
        the caller can mutate it freely).
    moves
        The ``len(moves) == n_plies`` move list reconstructed from the
        per-ply records, in play order. ``is_castling`` and
        ``is_en_passant`` flags are preserved.
    headers
        The ``game_header.headers`` block — typically
        ``{"termination", "n_plies"}`` plus ``"seed"`` when the writer
        knew one.
    """
    p = Path(path)
    records = [
        json.loads(line) for line in p.read_text(encoding="utf-8").splitlines()
    ]
    if not records:
        raise ValueError(f"{p} is empty — not a chess4d-ndjson-v1 file")
    fmt = records[0]
    if fmt.get("format") != NDJSON_FORMAT_ID:
        raise ValueError(
            f"{p} line 1 format={fmt.get('format')!r}, expected "
            f"{NDJSON_FORMAT_ID!r}"
        )
    if len(records) < 2 or records[1].get("type") != "game_header":
        raise ValueError(f"{p} line 2 is not a game_header record")
    headers: dict[str, Any] = dict(records[1].get("headers") or {})
    n_plies = int(headers.get("n_plies", len(records) - 3))
    if len(records) != n_plies + 3:
        raise ValueError(
            f"{p}: expected {n_plies + 3} lines "
            f"(format + game_header + {n_plies + 1} ply records), "
            f"got {len(records)}"
        )
    # Ply 0 sanity: pos4 must match the canonical starting position so
    # we're not silently encoding from the wrong root.
    ply0 = records[2]
    if ply0.get("ply") != 0:
        raise ValueError(f"{p}: line 3 ply={ply0.get('ply')!r}, expected 0")
    expected_pos4 = _pos4_compact(initial_position())
    if ply0.get("pos4") != expected_pos4:
        raise ValueError(
            f"{p}: ply-0 pos4 does not match initial_position(); "
            "mid-game-start NDJSON files are not supported by this "
            "version of the reader"
        )
    moves: list[Move4D] = []
    for i, rec in enumerate(records[3:], start=1):
        if rec.get("ply") != i:
            raise ValueError(
                f"{p}: record {i + 2} has ply={rec.get('ply')!r}, expected {i}"
            )
        from_list = rec.get("move_from")
        to_list = rec.get("move_to")
        if from_list is None or to_list is None:
            raise ValueError(
                f"{p}: ply {i} has null move_from/move_to — only ply 0 "
                "is allowed to omit the move"
            )
        promo_name = rec.get("move_promo")
        promotion = PieceType[promo_name] if promo_name is not None else None
        moves.append(
            Move4D(
                from_sq=Square4D(*from_list),
                to_sq=Square4D(*to_list),
                promotion=promotion,
                is_castling=bool(rec.get("is_castling", False)),
                is_en_passant=bool(rec.get("is_en_passant", False)),
            )
        )
    return initial_position(), moves, headers


# --- run id / manifest ------------------------------------------------------


def _auto_run_id(seed: Optional[int], *, now: Optional[datetime] = None) -> str:
    """Mint a default ``run_id`` from the UTC clock and seed.

    Format: ``corpus_YYYYMMDD_HHMMSS_seedNNN`` (or ``..._unseeded`` when
    no seed was supplied). ``now`` is an injection seam for tests — it
    defaults to ``datetime.now(timezone.utc)``.
    """
    stamp = (now or datetime.now(timezone.utc)).strftime("%Y%m%d_%H%M%S")
    tail = f"seed{seed}" if seed is not None else "unseeded"
    return f"corpus_{stamp}_{tail}"


def _tool_versions() -> dict[str, str]:
    """Best-effort ``tool_versions`` block for the manifest.

    Always reports ``python``. Tries :mod:`importlib.metadata` for
    ``chess4d`` (dist name ``python-chess4d-oana-chiru``) and
    ``chess_spectral``; missing packages (e.g. source checkout without
    an installed wheel, or ``chess_spectral`` absent because the extra
    wasn't installed) are silently skipped rather than failing the run.

    The manifest keys stay short (``chess4d``, ``chess_spectral``)
    regardless of upstream dist-name renames, so downstream consumers
    have a stable surface.
    """
    from importlib.metadata import PackageNotFoundError, version

    versions: dict[str, str] = {
        "python": f"{sys.version_info.major}.{sys.version_info.minor}."
        f"{sys.version_info.micro}",
    }
    # (manifest_key, distribution_name)
    probes = (
        ("chess4d", "python-chess4d-oana-chiru"),
        ("chess_spectral", "chess_spectral"),
    )
    for key, dist in probes:
        try:
            versions[key] = version(dist)
        except PackageNotFoundError:
            continue
    return versions


def _write_manifest(
    run_dir: Path,
    *,
    run_id: str,
    fetch_params: dict[str, Any],
    aggregates: dict[str, Any],
    games: list[GameSummary],
) -> Path:
    """Serialize ``manifest.json`` for one corpus run; return the path.

    The ``games`` list maps :class:`GameSummary` into the compact
    schema in the plan: per-game rows carry relative paths (so the
    run directory is relocatable), byte sizes, and the pivot ply for
    tail-encoded spectralz. ``spectralz`` / ``spectralz_bytes`` are
    ``None`` when encoding was skipped.
    """
    games_block: list[dict[str, Any]] = []
    for i, g in enumerate(games, start=1):
        games_block.append(
            {
                "index": i,
                "stem": g.stem,
                "c4d": f"c4d/{g.c4d_path.name}",
                "ndjson": f"ndjson/{g.ndjson_path.name}",
                "spectralz": (
                    f"spectralz/{g.encoding_path.name}"
                    if g.encoding_path is not None
                    else None
                ),
                "c4d_bytes": g.c4d_bytes,
                "ndjson_bytes": g.ndjson_bytes,
                "spectralz_bytes": (
                    g.encoding_bytes if g.encoding_path is not None else None
                ),
                "plies": g.plies,
                "encoded_plies": g.encoded_plies,
                "pivot_ply": g.pivot_ply,
                "termination": g.termination,
            }
        )
    manifest: dict[str, Any] = {
        "generated_utc": datetime.now(timezone.utc).isoformat(),
        "run_id": run_id,
        "source": "random_playout",
        "fetch_params": fetch_params,
        "tool_versions": _tool_versions(),
        "aggregates": aggregates,
        "games": games_block,
    }
    path = run_dir / "manifest.json"
    path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return path


# --- encoding dispatch ------------------------------------------------------


def encode_ndjson_to_spectralz(
    ndjson_path: str | Path,
    spectralz_path: str | Path,
    *,
    last_n: Optional[int] = None,
    use_native: Optional[bool] = None,
) -> tuple[int, int, int]:
    """NDJSON → spectralz adapter. Returns ``(pivot, encoded_plies, nbytes)``.

    Reads the chess4d-ndjson-v1 file at ``ndjson_path`` to recover the
    full ``(start_state, moves)`` pair, then writes the corresponding
    spectralz v4 file at ``spectralz_path``.

    ``last_n`` truncates the encoded range to the final ``last_n``
    plies (matching the ``--encode-last`` corpus CLI flag); frames
    carry absolute ply numbers via ``write_spectralz(..., base_ply=...)``
    so they line up with the NDJSON and c4d sidecars. ``last_n=None``
    encodes the entire game.

    ``use_native`` selects between the pure-Python and the bundled C
    encoder paths:

    * ``None`` (default) — auto-detect: use the C ``spectral_4d``
      binary if it's available in ``chess_spectral._native``, fall
      back to Python ``encode_4d`` if not. The C path is materially
      faster on big corpora; the two paths agree to within float32
      precision (the Python path emits tiny ``2^-55`` denormals in
      the A_1 channel from accumulation noise, the C path zeros them
      out — differences ≈ 1e-17, ten orders of magnitude below
      float32 epsilon).
    * ``True`` — require the C binary; raise
      :class:`chess4d.native_encoder.NativeEncoderUnavailable` if
      none is found (e.g. on the ``py3-none-any`` fallback wheel).
    * ``False`` — force the pure-Python path even when a C binary is
      installed. Useful for deterministic-bit-pattern reproducibility
      against the legacy reference output.

    Because the NDJSON carries all the information the encoder needs —
    the full move list plus ``is_castling`` / ``is_en_passant`` flags —
    this function is the canonical path for *retro-encoding* an
    existing ``--no-encode`` corpus (see :func:`encode_existing_run`).
    Lazily imports :mod:`chess4d.spectral` and
    :mod:`chess4d.native_encoder` so the NDJSON writer itself remains
    usable on a bare install without the ``[spectral]`` extra.
    """
    if use_native is None:
        from chess4d.native_encoder import locate_native_binary
        use_native = locate_native_binary() is not None
    if use_native:
        from chess4d.native_encoder import encode_ndjson_via_native
        return encode_ndjson_via_native(
            ndjson_path, spectralz_path, last_n=last_n
        )

    from chess4d.spectral import write_spectralz  # lazy import

    start, moves, _ = read_ndjson_game(ndjson_path)
    total = len(moves)
    pivot = max(0, total - last_n) if last_n is not None else 0
    tail_start = copy.deepcopy(start)
    for m in moves[:pivot]:
        tail_start.push(m)
    tail_moves = moves[pivot:]
    nbytes = write_spectralz(
        spectralz_path, tail_start, tail_moves, base_ply=pivot
    )
    return pivot, len(tail_moves), nbytes


def _encode_one_game(
    ndjson_path: Path,
    spectralz_path: Path,
    *,
    encode_last: Optional[int],
    use_native: Optional[bool] = None,
) -> tuple[int, int, int]:
    """Thin ``generate_corpus``-internal wrapper over the NDJSON path.

    Kept as a private dispatch seam so the two-pass flow inside
    ``generate_corpus`` has a single place to add cross-cutting
    concerns (progress bars, error capture, …) without growing the
    public :func:`encode_ndjson_to_spectralz` signature.
    """
    return encode_ndjson_to_spectralz(
        ndjson_path, spectralz_path, last_n=encode_last, use_native=use_native
    )


# --- corpus entry point -----------------------------------------------------


def generate_corpus(
    n_games: int,
    *,
    max_plies: int = 200,
    seed: Optional[int] = None,
    output_dir: str | Path = "./corpus",
    encode: bool = True,
    encode_last: Optional[int] = None,
    run_id: Optional[str] = None,
    use_native: Optional[bool] = None,
) -> CorpusResult:
    """Generate ``n_games`` random-playout games under a new run directory.

    Layout mirrors ``chess-maths-the-movie``: ``output_dir`` is treated
    as the parent, and the artifacts land under a freshly-created
    ``<output_dir>/<run_id>/`` subdirectory. Each game produces a
    compact ``.c4d`` move log and an NDJSON per-ply record stream;
    spectralz output is optional and controlled by ``encode`` /
    ``encode_last``.

    ``encode_last`` restricts the spectralz encoding to the final N
    plies of each game — the c4d and NDJSON sidecars always carry the
    full move list. ``encode=False`` and a non-``None`` ``encode_last``
    together are contradictory and the CLI rejects them up front.

    ``seed`` fully determines the random-playout output: two calls
    with the same ``(n_games, max_plies, seed)`` produce byte-identical
    c4d and NDJSON files. Spectralz reproducibility depends on the
    encoder choice — see ``use_native``.

    ``use_native`` selects the spectralz encoder backend:

    * ``None`` (default) — auto: native C binary if installed, else
      Python ``encode_4d``.
    * ``True`` — require the C binary; raise if absent.
    * ``False`` — force Python encoder.

    See :func:`encode_ndjson_to_spectralz` for the parity story.

    When ``run_id`` is ``None`` a fresh one is minted from the UTC
    clock (see :func:`_auto_run_id`), so back-to-back runs land in
    distinct directories.
    """
    if not encode and encode_last is not None:
        raise ValueError(
            "encode=False and encode_last are mutually exclusive; "
            "disable one."
        )
    resolved_run_id = run_id if run_id is not None else _auto_run_id(seed)
    out_root = Path(output_dir)
    run_dir = out_root / resolved_run_id
    c4d_dir = run_dir / "c4d"
    ndjson_dir = run_dir / "ndjson"
    run_dir.mkdir(parents=True, exist_ok=True)
    c4d_dir.mkdir(parents=True, exist_ok=True)
    ndjson_dir.mkdir(parents=True, exist_ok=True)
    spectralz_dir: Optional[Path] = None
    if encode:
        spectralz_dir = run_dir / "spectralz"
        spectralz_dir.mkdir(parents=True, exist_ok=True)
    rng = random.Random(seed)
    summaries: list[GameSummary] = []
    wall_start = time.monotonic()
    for i in range(1, n_games + 1):
        stem = f"game_{i:03d}"
        moves, termination = play_random_game(rng, max_plies)
        c4d_path = c4d_dir / f"{stem}.c4d"
        ndjson_path = ndjson_dir / f"{stem}.ndjson"
        write_game_file(c4d_path, initial_position(), moves)
        c4d_bytes = c4d_path.stat().st_size
        ndjson_bytes = write_ndjson_game(
            ndjson_path,
            initial_position(),
            moves,
            termination=termination,
            game_index=i - 1,
            seed=seed,
        )
        encoding_path: Optional[Path] = None
        encoded_plies = 0
        encoding_bytes = 0
        pivot = 0
        if encode:
            assert spectralz_dir is not None  # mkdir above
            encoding_path = spectralz_dir / f"{stem}.spectralz"
            # Two-pass: we already wrote the NDJSON above; drive the
            # spectralz encoder off that sidecar rather than the
            # in-memory move list. The NDJSON is the bridge between
            # generation and encoding, so adding a standalone
            # retro-encode command (see encode_existing_run) becomes
            # a pure second-pass over the same bytes.
            pivot, encoded_plies, encoding_bytes = _encode_one_game(
                ndjson_path,
                encoding_path,
                encode_last=encode_last,
                use_native=use_native,
            )
        summaries.append(
            GameSummary(
                stem=stem,
                c4d_path=c4d_path,
                ndjson_path=ndjson_path,
                encoding_path=encoding_path,
                plies=len(moves),
                encoded_plies=encoded_plies,
                pivot_ply=pivot,
                termination=termination,
                c4d_bytes=c4d_bytes,
                ndjson_bytes=ndjson_bytes,
                encoding_bytes=encoding_bytes,
            )
        )
        tail_tag = (
            f" encoded_plies={encoded_plies:4d} pivot={pivot:4d}"
            if encode and encode_last is not None
            else ""
        )
        bytes_tag = f" bytes={encoding_bytes}" if encode else " no-encode"
        print(
            f"{stem}: plies={len(moves):4d} "
            f"term={termination:10s}{tail_tag}{bytes_tag}",
            file=sys.stderr,
        )
    wall_time_s = time.monotonic() - wall_start
    fetch_params: dict[str, Any] = {
        "n_games": n_games,
        "max_plies": max_plies,
        "seed": seed,
        "encode": encode,
        "encode_last": encode_last,
    }
    aggregates: dict[str, Any] = {
        "n_games": len(summaries),
        "n_encoded_games": sum(1 for s in summaries if s.encoding_path is not None),
        "total_plies": sum(s.plies for s in summaries),
        "total_encoded_plies": sum(s.encoded_plies for s in summaries),
        "n_errors": 0,
        "wall_time_s": round(wall_time_s, 3),
    }
    manifest_path = _write_manifest(
        run_dir,
        run_id=resolved_run_id,
        fetch_params=fetch_params,
        aggregates=aggregates,
        games=summaries,
    )
    return CorpusResult(
        run_dir=run_dir,
        run_id=resolved_run_id,
        manifest_path=manifest_path,
        games=summaries,
    )


# --- retro-encode pass ------------------------------------------------------


def encode_existing_run(
    run_dir: str | Path,
    *,
    last_n: Optional[int] = None,
    use_native: Optional[bool] = None,
) -> CorpusResult:
    """Retro-encode an existing ``--no-encode`` corpus; return fresh :class:`CorpusResult`.

    The run directory must contain a ``manifest.json`` (written by a
    prior :func:`generate_corpus` call) and one ``ndjson/*.ndjson`` per
    game row. This function:

    1. creates ``run_dir/spectralz/`` if missing,
    2. feeds each NDJSON through :func:`encode_ndjson_to_spectralz`,
       writing ``spectralz/game_NNN.spectralz`` with absolute ply
       numbers (``last_n`` honored per-game),
    3. rewrites ``manifest.json`` in place so ``fetch_params.encode``,
       ``fetch_params.encode_last``, ``aggregates.n_encoded_games``,
       ``aggregates.total_encoded_plies``, and each ``games[i]``
       ``spectralz`` / ``spectralz_bytes`` / ``encoded_plies`` /
       ``pivot_ply`` row reflects the new encoding,
    4. returns a :class:`CorpusResult` for the updated run.

    ``use_native`` selects the encoder backend (auto / native /
    Python) — see :func:`encode_ndjson_to_spectralz` for semantics.

    Within-backend reproducibility: for a given (seed, last_n,
    backend), running ``generate_corpus(..., encode_last=N)`` and
    ``generate_corpus(..., encode=False)`` followed by
    ``encode_existing_run(run_dir, last_n=N)`` produce the same
    spectralz bytes. Cross-backend (Python vs native) bytes match to
    within float32 precision but differ in the A_1 channel by tiny
    accumulation noise (~1e-17, well below float32 epsilon).
    """
    run_path = Path(run_dir)
    manifest_path = run_path / "manifest.json"
    if not manifest_path.is_file():
        raise FileNotFoundError(f"no manifest.json under {run_path}")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    spectralz_dir = run_path / "spectralz"
    spectralz_dir.mkdir(parents=True, exist_ok=True)

    # Reload per-game fields from the existing manifest, then fill in
    # the fresh encoding output. The c4d / NDJSON rows are untouched.
    summaries: list[GameSummary] = []
    for row in manifest["games"]:
        stem = row["stem"]
        c4d_path = run_path / row["c4d"]
        ndjson_path = run_path / row["ndjson"]
        spectralz_path = spectralz_dir / f"{stem}.spectralz"
        pivot, encoded_plies, encoding_bytes = encode_ndjson_to_spectralz(
            ndjson_path,
            spectralz_path,
            last_n=last_n,
            use_native=use_native,
        )
        summaries.append(
            GameSummary(
                stem=stem,
                c4d_path=c4d_path,
                ndjson_path=ndjson_path,
                encoding_path=spectralz_path,
                plies=int(row["plies"]),
                encoded_plies=encoded_plies,
                pivot_ply=pivot,
                termination=row["termination"],
                c4d_bytes=int(row["c4d_bytes"]),
                ndjson_bytes=int(row["ndjson_bytes"]),
                encoding_bytes=encoding_bytes,
            )
        )
        print(
            f"{stem}: plies={int(row['plies']):4d} "
            f"term={row['termination']:10s} "
            f"encoded_plies={encoded_plies:4d} pivot={pivot:4d} "
            f"bytes={encoding_bytes}",
            file=sys.stderr,
        )

    # Fresh fetch_params / aggregates reflecting the new encoding pass.
    prior = manifest.get("fetch_params", {})
    fetch_params: dict[str, Any] = dict(prior)
    fetch_params["encode"] = True
    fetch_params["encode_last"] = last_n
    aggregates: dict[str, Any] = {
        "n_games": len(summaries),
        "n_encoded_games": len(summaries),
        "total_plies": sum(s.plies for s in summaries),
        "total_encoded_plies": sum(s.encoded_plies for s in summaries),
        "n_errors": 0,
        "wall_time_s": float(manifest.get("aggregates", {}).get("wall_time_s", 0.0)),
    }
    new_manifest_path = _write_manifest(
        run_path,
        run_id=manifest["run_id"],
        fetch_params=fetch_params,
        aggregates=aggregates,
        games=summaries,
    )
    return CorpusResult(
        run_dir=run_path,
        run_id=manifest["run_id"],
        manifest_path=new_manifest_path,
        games=summaries,
    )


# --- CLI --------------------------------------------------------------------


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="chess4d-corpus-gen",
        description="Generate a chess4d random-playout corpus under "
        "<output>/<run_id>/ with manifest.json + c4d/ + ndjson/ + "
        "spectralz/ (layout mirrors chess-maths-the-movie).",
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
        help="Parent directory; the run lands under <output>/<run_id>/.",
    )
    parser.add_argument(
        "--run-id",
        type=str,
        default=None,
        metavar="ID",
        help="Override the auto-generated run_id subdirectory name "
        "(default: corpus_YYYYMMDD_HHMMSS_seedNNN).",
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--encode-last",
        type=int,
        default=None,
        metavar="N",
        help="Encode only the final N plies into spectralz; the c4d "
        "and NDJSON sidecars still carry the full move list. Frames "
        "carry absolute ply numbers.",
    )
    group.add_argument(
        "--no-encode",
        action="store_true",
        help="Skip spectralz output entirely; emit only c4d and NDJSON.",
    )
    parser.add_argument(
        "--encoder",
        choices=("auto", "python", "native"),
        default="auto",
        help="Spectralz encoder backend. ``auto`` (default) uses the "
        "bundled C ``spectral_4d`` binary if installed via "
        "chess-spectral, otherwise falls back to the Python encoder. "
        "``native`` requires the C binary; ``python`` forces the pure-"
        "Python path. The two paths agree to within float32 precision "
        "(see CHANGELOG [0.4.0]).",
    )
    parser.add_argument(
        "--move-operator",
        choices=("spatial", "phase"),
        default="spatial",
        help="Random-playout move generator. ``spatial`` (default) "
        "uses chess4d's geometric legal-move generator. ``phase`` "
        "would route through chess_spectral.phase_operators_4d but "
        "is not yet wired up — the flag is reserved here for the "
        "follow-up PR. Selecting ``phase`` raises NotImplementedError.",
    )
    return parser


def main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point. Returns the process exit code."""
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.move_operator == "phase":
        raise NotImplementedError(
            "--move-operator phase is reserved for a follow-up PR; "
            "use --move-operator spatial (default) for now"
        )
    use_native: Optional[bool]
    if args.encoder == "auto":
        use_native = None
    elif args.encoder == "python":
        use_native = False
    else:
        use_native = True
    result = generate_corpus(
        n_games=args.n_games,
        max_plies=args.max_plies,
        seed=args.seed,
        output_dir=args.output,
        encode=not args.no_encode,
        encode_last=args.encode_last,
        run_id=args.run_id,
        use_native=use_native,
    )
    total_encoded_bytes = sum(s.encoding_bytes for s in result.games)
    total_plies = sum(s.plies for s in result.games)
    total_encoded_plies = sum(s.encoded_plies for s in result.games)
    print(
        f"wrote {len(result.games)} games, {total_plies} plies "
        f"(encoded {total_encoded_plies}), "
        f"{total_encoded_bytes} spectralz bytes to {result.run_dir}",
        file=sys.stderr,
    )
    return 0


def _build_encode_parser() -> argparse.ArgumentParser:
    """Argument parser for the retro-encode CLI (``chess4d-corpus-encode``)."""
    parser = argparse.ArgumentParser(
        prog="chess4d-corpus-encode",
        description="Encode spectralz files for an existing chess4d "
        "corpus run directory. Reads each ndjson/*.ndjson, writes "
        "spectralz/*.spectralz with absolute ply numbers, and updates "
        "manifest.json in place. Requires the [spectral] extra.",
    )
    parser.add_argument(
        "run_dir",
        type=Path,
        help="Corpus run directory (must contain manifest.json and ndjson/).",
    )
    parser.add_argument(
        "--last-n",
        type=int,
        default=None,
        metavar="N",
        help="Encode only the final N plies per game; frames carry "
        "absolute ply numbers. Omit to encode the entire game.",
    )
    parser.add_argument(
        "--encoder",
        choices=("auto", "python", "native"),
        default="auto",
        help="Spectralz encoder backend; same semantics as "
        "``chess4d-corpus-gen --encoder``.",
    )
    return parser


def encode_main(argv: Optional[list[str]] = None) -> int:
    """CLI entry point for ``chess4d-corpus-encode``. Returns exit code."""
    parser = _build_encode_parser()
    args = parser.parse_args(argv)
    use_native: Optional[bool]
    if args.encoder == "auto":
        use_native = None
    elif args.encoder == "python":
        use_native = False
    else:
        use_native = True
    result = encode_existing_run(
        args.run_dir, last_n=args.last_n, use_native=use_native
    )
    total_encoded_bytes = sum(s.encoding_bytes for s in result.games)
    total_encoded_plies = sum(s.encoded_plies for s in result.games)
    print(
        f"encoded {len(result.games)} games, "
        f"{total_encoded_plies} plies, "
        f"{total_encoded_bytes} spectralz bytes in {result.run_dir}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
