"""Detect, normalize and count line endings in text."""

from __future__ import annotations

import re
from typing import Literal

Style = Literal["lf", "crlf", "cr"]
Detected = Literal["lf", "crlf", "cr", "mixed", "none"]

_PATTERN = re.compile(r"\r\n|\r|\n")
_NAME_OF = {"\r\n": "crlf", "\r": "cr", "\n": "lf"}
_SEQ_OF: dict[Style, str] = {"lf": "\n", "crlf": "\r\n", "cr": "\r"}


def counts(text: str) -> dict[str, int]:
    """Count each line ending, treating CRLF as one unit rather than CR plus LF."""
    tally = {"lf": 0, "crlf": 0, "cr": 0}
    for match in _PATTERN.finditer(text):
        tally[_NAME_OF[match.group()]] += 1
    return tally


def detect(text: str) -> Detected:
    """Report the line-ending style: one of the three kinds, "mixed", or "none"."""
    present = [name for name, count in counts(text).items() if count]
    if not present:
        return "none"
    if len(present) == 1:
        return present[0]  # type: ignore[return-value]
    return "mixed"


def normalize(text: str, to: Style = "lf") -> str:
    """Convert every line ending to the chosen style, including a lone CR."""
    try:
        replacement = _SEQ_OF[to]
    except KeyError:
        raise ValueError(f"unknown style: {to!r}") from None
    return _PATTERN.sub(replacement, text)
