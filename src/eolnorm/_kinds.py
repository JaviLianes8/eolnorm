"""Line-ending kinds, the boundary sets that group them and the patterns that find them."""

from __future__ import annotations

import re
from typing import Literal, cast

from ._checks import option

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
    "\N{LINE SEPARATOR}": "ls",
    "\N{PARAGRAPH SEPARATOR}": "ps",
}
# UAX #14: BK (VT, FF, LS, PS), CR, LF and NL are the mandatory breaks. str.splitlines
# also splits on the three information separators FS, GS and RS.
_SETS: dict[Breaks, str] = {
    "ascii": "\n\r",
    "unicode": "\n\r\x0b\x0c\x85\N{LINE SEPARATOR}\N{PARAGRAPH SEPARATOR}",
    "splitlines": "\n\r\x0b\x0c\x1c\x1d\x1e\x85\N{LINE SEPARATOR}\N{PARAGRAPH SEPARATOR}",
}
_SEQUENCES: dict[Style, str] = {"lf": "\n", "crlf": "\r\n", "cr": "\r"}


def check_breaks(breaks: object) -> Breaks:
    return cast(Breaks, option("boundary set", breaks, _SETS))


def check_style(to: object) -> Style:
    return cast(Style, option("style", to, _SEQUENCES))


def kinds(breaks: Breaks) -> tuple[Kind, ...]:
    """The kinds a boundary set recognises: lf, crlf, cr first, then the rest."""
    names = [_CHARS[char] for char in _SETS[breaks]]
    return ("lf", "crlf", "cr", *names[2:])


def sequence(to: Style) -> str:
    return _SEQUENCES[to]


def tally(text: str | bytes, breaks: Breaks) -> dict[str, int]:
    """Count the endings of exact, checked input, keys in the order of ``kinds``.

    CRLF is the only two-character ending and no two CRLFs can overlap, so every CR and LF
    beyond the CRLF pairs is a lone one; the other kinds are single characters.
    """
    if isinstance(text, bytes):
        pairs = text.count(b"\r\n")
        return {"lf": text.count(b"\n") - pairs, "crlf": pairs, "cr": text.count(b"\r") - pairs}
    pairs = text.count("\r\n")
    counted = {"lf": text.count("\n") - pairs, "crlf": pairs, "cr": text.count("\r") - pairs}
    for char in _SETS[breaks][2:]:
        counted[_CHARS[char]] = text.count(char)
    return counted


def _build(chars: str) -> re.Pattern[str]:
    return re.compile("\r\n|[" + re.escape(chars) + "]")


# Every ending of a set, and the same without a lone CR (for keep_lone_cr): a CR is then
# matched only as the start of a CRLF, so a lone one is never touched.
_TEXT = {breaks: _build(chars) for breaks, chars in _SETS.items()}
_TEXT_KEEP = {breaks: _build(chars.replace("\r", "")) for breaks, chars in _SETS.items()}
_BYTES = re.compile(rb"\r\n|[\r\n]")
_BYTES_KEEP = re.compile(rb"\r\n|\n")


def text_pattern(breaks: Breaks, keep_lone_cr: bool = False) -> re.Pattern[str]:
    return (_TEXT_KEEP if keep_lone_cr else _TEXT)[breaks]


def bytes_pattern(keep_lone_cr: bool = False) -> re.Pattern[bytes]:
    return _BYTES_KEEP if keep_lone_cr else _BYTES
