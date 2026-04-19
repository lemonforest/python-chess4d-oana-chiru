"""Exceptions for the chess4d notation layer (Phase 7).

Parsers in :mod:`chess4d.notation.compact` and
:mod:`chess4d.notation.json_format` raise :class:`NotationError` for all
syntactic failures. It is a subclass of :class:`ValueError` so that
callers who only care about the general "bad input" shape can catch the
stdlib type without importing this module.
"""

from __future__ import annotations


class NotationError(ValueError):
    """Raised when a notation parser rejects an input string.

    Error messages include the offending input fragment and a short
    description of what was expected. Parsers fail fast on the first
    problem — they do not collect multiple errors into a single raise.
    """
