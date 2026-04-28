"""Native (C) encoder integration — chess-spectral 1.3.1+.

Bridges :mod:`chess4d.corpus`'s NDJSON sidecars to the bundled C
``spectral_4d`` binary that ships inside the ``chess-spectral``
platform wheels at ``chess_spectral/_native/spectral_4d.exe``
(or the platform-equivalent name on Linux/macOS).

The native binary produces the same v4 spectralz output as the Python
:func:`chess_spectral.encoder_4d.encode_4d` adapter we already use,
but materially faster on large corpora — see CHANGELOG [0.4.0].

Public API
----------
* :func:`encode_ndjson_via_native` — main entry point. Translates a
  ``chess4d-ndjson-v1`` file into the upstream ``NDJSON4`` schema
  expected by ``spectral_4d encode``, invokes the binary, and writes
  the resulting v4 ``.spectralz`` to the requested path.
* :func:`locate_native_binary` — returns the on-disk path of the
  bundled binary, or ``None`` if the installed ``chess-spectral`` is
  the pure-Python ``py3-none-any`` fallback wheel.

Design notes
------------
* The schema translation is in this module rather than in
  ``chess4d.corpus`` because it's an integration concern; nobody
  upstream cares about ``chess4d-ndjson-v1`` and we don't want to
  push the FEN4 serializer into the corpus writer.
* ``last_n`` is honored client-side by slicing the NDJSON4 we hand
  to the binary — the C binary's ``encode`` subcommand currently has
  no ``--start/--count`` flags. Output ``ply`` numbers stay absolute.
* The binary's NDJSON4 schema (per ``chess-spectral-4d encode-moves4
  --help``): one line per ply with ``{ply, fen4, move_from?,
  move_to?, promo?, flags?}``. Lines without move metadata describe
  the initial position; subsequent lines carry the move that
  produced them. Output is ``decompressed-byte-identical`` to the
  pure-Python encoder per upstream's parity guarantee.
"""

from __future__ import annotations

import copy
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional

from chess4d.corpus import read_ndjson_game


__all__ = [
    "NativeEncoderError",
    "NativeEncoderUnavailable",
    "encode_ndjson_via_native",
    "locate_native_binary",
    "pos4_to_fen4",
]


# Upstream FEN4 v1 prefix (see chess_spectral.fen_4d.PREFIX).
_FEN4_PREFIX = "4d-fen v1:"


class NativeEncoderError(RuntimeError):
    """Raised when the native binary fails or its output is unusable."""


class NativeEncoderUnavailable(RuntimeError):
    """Raised when ``use_native=True`` is requested but no binary is found."""


def locate_native_binary() -> Optional[Path]:
    """Return the path to the bundled ``spectral_4d`` binary, or ``None``.

    The C binary ships inside chess-spectral's platform wheels at
    ``<site-packages>/chess_spectral/_native/spectral_4d{.exe?}``.
    Pure-Python (``py3-none-any``) wheels don't carry it; in that
    case (or if chess-spectral isn't installed at all) we return
    ``None`` and the caller should fall back to the Python encoder.

    Linux / macOS ship ``spectral_4d`` (no extension); Windows ships
    ``spectral_4d.exe``. We try both names regardless of platform —
    the binary is the same C17 source compiled per-platform.
    """
    try:
        import chess_spectral
    except ImportError:
        return None
    base = Path(chess_spectral.__file__).resolve().parent / "_native"
    if not base.is_dir():
        return None
    for name in ("spectral_4d.exe", "spectral_4d"):
        candidate = base / name
        if candidate.is_file():
            return candidate
    # Last-ditch: ``shutil.which`` in case the user has it on PATH.
    on_path = shutil.which("spectral_4d") or shutil.which("spectral_4d.exe")
    return Path(on_path) if on_path else None


# --- pos4 -> FEN4 v1 serializer ---------------------------------------------

# Inverse of chess_spectral.fen_4d.parse: a non-pawn piece is a single
# character (uppercase white, lowercase black); a pawn is a 2-char
# (color_char, axis_char) tuple — same shape :func:`chess4d.spectral.
# gamestate_to_pos4` emits.

_NONPAWN_CHARS = {"K", "Q", "R", "B", "N", "k", "q", "r", "b", "n"}


def pos4_to_fen4(pos4: dict[Any, Any]) -> str:
    """Serialize a ``pos4`` dict into a FEN4 v1 placement literal.

    ``pos4`` keys are linear square indices ``(x*8+y)*8+z)*8+w`` —
    int *or* str-coerced int (the chess4d-ndjson-v1 sidecar uses
    string keys to be JSON-safe; the in-memory form from
    :func:`chess4d.corpus._pos4_compact` does the same). Values are
    either a single character (non-pawn, case-encoded color) or a
    ``(color_char, axis_char)`` tuple / list (pawn — JSON round-trip
    turns tuples into lists).

    Empty boards return just ``"4d-fen v1:"`` with no placements.
    The output round-trips through
    :func:`chess_spectral.fen_4d.parse` to a dict equal to the
    input modulo str/int key coercion.
    """
    # Normalize keys to int (NDJSON loads them as str).
    norm: dict[int, Any] = {int(k): v for k, v in pos4.items()}
    placements: list[str] = []
    _pawn_strs = {"Pw", "Py", "pw", "py"}
    # Sorted by linear index so the output is deterministic.
    for idx in sorted(norm.keys()):
        v = norm[idx]
        if isinstance(v, (tuple, list)) and len(v) == 2:
            # ``chess4d.spectral.gamestate_to_pos4`` form: (color, axis).
            color_char, axis_char = v
            piece_str = f"{color_char}{axis_char}"
        elif isinstance(v, str):
            # ``chess4d.corpus._pos4_compact`` form: 1-char non-pawn or
            # 2-char pawn (color + axis, e.g. "Pw", "py").
            if v in _pawn_strs or v in _NONPAWN_CHARS:
                piece_str = v
            else:
                raise ValueError(
                    f"unrecognized pos4 piece string {v!r} at index {idx}"
                )
        else:
            raise ValueError(
                f"unrecognized pos4 value type {type(v).__name__} "
                f"at index {idx}: {v!r}"
            )
        # Linear index back to (x, y, z, w).
        x = (idx >> 9) & 7
        y = (idx >> 6) & 7
        z = (idx >> 3) & 7
        w = idx & 7
        placements.append(f"{piece_str}@{x},{y},{z},{w}")
    return _FEN4_PREFIX + ";".join(placements)


# --- pos4 trajectory recovery -----------------------------------------------


def _replay_pos4_sequence(
    src_ndjson: Path,
) -> tuple[list[int], list[dict[str, Any]], list[Optional[dict[str, Any]]]]:
    """Replay the NDJSON game and return (plies, pos4s, move_records).

    Each item at index *i* corresponds to the *i*-th ply record in
    the source NDJSON. ``move_records[i]`` is ``None`` for the
    starting frame (ply 0) and a dict carrying ``move_from``,
    ``move_to``, ``move_promo``, ``is_castling``, ``is_en_passant``
    for subsequent plies.

    We recompute pos4s by replaying moves rather than reading the
    NDJSON's ``pos4`` field directly because the latter is
    informational only — replay is the source of truth and matches
    what :func:`chess4d.spectral.write_spectralz` does internally.
    """
    from chess4d.corpus import _pos4_compact

    start_state, moves, _headers = read_ndjson_game(src_ndjson)
    current = copy.deepcopy(start_state)
    pos4s: list[dict[str, Any]] = [_pos4_compact(current)]
    move_records: list[Optional[dict[str, Any]]] = [None]
    for m in moves:
        current.push(m)
        pos4s.append(_pos4_compact(current))
        move_records.append(
            {
                "move_from": [m.from_sq.x, m.from_sq.y, m.from_sq.z, m.from_sq.w],
                "move_to": [m.to_sq.x, m.to_sq.y, m.to_sq.z, m.to_sq.w],
                "move_promo": m.promotion.name if m.promotion is not None else None,
                "is_castling": bool(m.is_castling),
                "is_en_passant": bool(m.is_en_passant),
            }
        )
    plies = list(range(len(pos4s)))
    return plies, pos4s, move_records


# --- chess4d-ndjson-v1 -> upstream NDJSON4 ----------------------------------


def _flags_from_move_record(rec: Optional[dict[str, Any]]) -> int:
    """Pack ``is_castling`` and ``is_en_passant`` into a flag bitfield.

    The upstream NDJSON4 schema documents ``flags`` as an optional
    int with bit semantics defined in
    ``docs/NDJSON4_FORMAT.md``. We mirror the Frame4D convention
    used in :class:`chess_spectral.frame_4d.Frame4D` write path:
    bit 0 = is_castling, bit 1 = is_en_passant. Frame4D readers
    on the chess-spectral side ignore bits they don't recognize.
    """
    if rec is None:
        return 0
    flags = 0
    if rec.get("is_castling"):
        flags |= 1 << 0
    if rec.get("is_en_passant"):
        flags |= 1 << 1
    return flags


def _write_ndjson4(
    dst: Path,
    plies: list[int],
    pos4s: list[dict[str, Any]],
    move_records: list[Optional[dict[str, Any]]],
    *,
    last_n: Optional[int],
) -> tuple[int, int]:
    """Write the upstream-NDJSON4 file. Returns (pivot, encoded_plies).

    ``pivot`` is the absolute index of the first emitted record
    (``0`` when ``last_n is None``). When ``last_n`` is set, only
    the final ``last_n + 1`` records (last_n moves + the position
    they were applied to) are written, with the pivot's record
    flagged as a "starting position" (no move metadata).
    """
    total = len(plies)
    if last_n is None:
        pivot = 0
        emitted = total
    else:
        pivot = max(0, total - 1 - last_n)
        emitted = total - pivot

    with dst.open("w", encoding="utf-8") as f:
        for i, (ply, pos4, mrec) in enumerate(
            zip(plies[pivot:], pos4s[pivot:], move_records[pivot:])
        ):
            line: dict[str, Any] = {"ply": ply, "fen4": pos4_to_fen4(pos4)}
            # First emitted line is the starting state for the encoded
            # window — strip move metadata so the binary's encoder treats
            # it as the pivot frame (matching Python's leading sentinel).
            if i > 0 and mrec is not None:
                line["move_from"] = mrec["move_from"]
                line["move_to"] = mrec["move_to"]
                if mrec["move_promo"] is not None:
                    line["move_promo"] = mrec["move_promo"]
                line["flags"] = _flags_from_move_record(mrec)
            f.write(json.dumps(line, sort_keys=True) + "\n")
    encoded_plies = emitted - 1  # the pivot frame doesn't count as encoded
    return pivot, max(encoded_plies, 0)


# --- top-level entry point --------------------------------------------------


def encode_ndjson_via_native(
    src_ndjson: str | Path,
    dst_spectralz: str | Path,
    *,
    last_n: Optional[int] = None,
    binary: Optional[Path] = None,
) -> tuple[int, int, int]:
    """NDJSON → spectralz via the native C ``spectral_4d`` binary.

    Mirrors :func:`chess4d.corpus.encode_ndjson_to_spectralz` but
    routes through the bundled C binary instead of Python
    ``encode_4d``. Returns ``(pivot_ply, encoded_plies, nbytes)``.

    ``binary`` defaults to whatever :func:`locate_native_binary`
    finds; pass an explicit path if you have a non-bundled build.

    Raises
    ------
    NativeEncoderUnavailable
        If ``binary`` is ``None`` and no bundled binary was found.
    NativeEncoderError
        If the binary exits non-zero or produces no output.
    """
    bin_path = Path(binary) if binary is not None else locate_native_binary()
    if bin_path is None:
        raise NativeEncoderUnavailable(
            "no chess-spectral native binary found; install a "
            "chess-spectral platform wheel (cp310/cp311/cp312/cp313/"
            "cp314 + win_amd64 / manylinux / macOS) or pass an explicit "
            "binary= path"
        )
    src = Path(src_ndjson)
    dst = Path(dst_spectralz)

    # Replay -> pos4 trajectory -> upstream NDJSON4.
    plies, pos4s, move_records = _replay_pos4_sequence(src)
    with tempfile.TemporaryDirectory() as tmp:
        ndjson4_path = Path(tmp) / "input.ndjson4"
        pivot, encoded_plies = _write_ndjson4(
            ndjson4_path, plies, pos4s, move_records, last_n=last_n
        )
        # Invoke the binary. ``spectral_4d encode -i <ndjson4> -o <out>``.
        cmd = [
            str(bin_path),
            "encode",
            "-i",
            str(ndjson4_path),
            "-o",
            str(dst),
        ]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode != 0:
            raise NativeEncoderError(
                f"spectral_4d encode failed (rc={result.returncode}):\n"
                f"  stderr: {result.stderr.strip()[:500]}\n"
                f"  stdout: {result.stdout.strip()[:200]}"
            )
        if not dst.exists():
            raise NativeEncoderError(
                f"spectral_4d encode reported success but {dst} was not "
                "created"
            )
        nbytes = dst.stat().st_size
    return pivot, encoded_plies, nbytes


def _self_smoke() -> int:  # pragma: no cover — manual sanity probe
    """Quick CLI: ``python -m chess4d.native_encoder`` to print the binary path."""
    p = locate_native_binary()
    if p is None:
        print("no native binary found", file=sys.stderr)
        return 1
    print(p)
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(_self_smoke())
