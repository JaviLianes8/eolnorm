"""Line-ending kinds, the boundary sets that group them and the patterns that find them."""

from __future__ import annotations

import re
from typing import Literal

Style = Literal["lf", "crlf", "cr"]
Kind = Literal["lf", "crlf", "cr", "vt", "ff", "fs", "gs", "rs", "nel", "ls", "ps"]
Detected = Kind | Literal["mixed", "none"]
Breaks = Literal["ascii", "unicode", "splitlines"]

# Single-character kinds in report order. CRLF is the only two-character ending.
_CHARS: dict[str, Kind] = {
    "\n": "lf",
    "\r": "cr",
    "\x0b": "vt",
    "\x0c": "ff",
    "\x1c": "fs",
    "\x1d": "gs",
    "\x1e": "rs",
    "\x85": "nel",
    "\u2028": "ls",
    "\u2029": "ps",
}
# UAX #14: BK (VT, FF, LS, PS), CR, LF and NL are the mandatory breaks. str.splitlines
# also splits on the three information separators FS, GS and RS.
_SETS: dict[Breaks, str] = {
    "ascii": "\n\r",
    "unicode": "\n\r\x0b\x0c\x85\u2028\u2029",
    "splitlines": "\n\r\x0b\x0c\x1c\x1d\x1e\x85\u2028\u2029",
}
_SEQUENCES: dict[Style, str] = {"lf": "\n", "crlf": "\r\n", "cr": "\r"}


def check_breaks(breaks: object) -> Breaks:
    if not isinstance(breaks, str) or breaks not in _SETS:
        raise ValueError(f"unknown boundary set: {breaks!r}")
    return breaks


def check_style(to: object) -> Style:
    if not isinstance(to, str) or to not in _SEQUENCES:
        raise ValueError(f"unknown style: {to!r}")
    return to


def kinds(breaks: Breaks) -> tuple[Kind, ...]:
    """The kinds a boundary set recognises: lf, crlf, cr first, then the rest."""
    names = [_CHARS[char] for char in _SETS[breaks]]
    return ("lf", "crlf", "cr", *names[2:])


def name_of(ending: str) -> Kind:
    return "crlf" if ending == "\r\n" else _CHARS[ending]


def sequence(to: Style) -> str:
    return _SEQUENCES[to]


def _build(chars: str) -> re.Pattern[str]:
    return re.compile("\r\n|[" + re.escape(chars) + "]")


_TEXT_PATTERNS = {breaks: _build(chars) for breaks, chars in _SETS.items()}
BYTES_PATTERN = re.compile(rb"\r\n|[\r\n]")


def text_pattern(breaks: Breaks) -> re.Pattern[str]:
    return _TEXT_PATTERNS[breaks]
