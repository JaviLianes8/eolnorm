"""Detect, normalize and count line endings in text or bytes."""

from __future__ import annotations

from collections.abc import Mapping
from typing import AnyStr, cast

from ._checks import flag, text_or_bytes
from ._kinds import (
    Breaks,
    Detected,
    Style,
    bytes_pattern,
    check_breaks,
    check_style,
    sequence,
    tally,
    text_pattern,
)


def checked(text: object, breaks: object) -> tuple[str | bytes, Breaks]:
    """The exact input and boundary set, once both are known to be acceptable together."""
    exact = text_or_bytes(text)
    chosen = check_breaks(breaks)
    if isinstance(exact, bytes) and chosen != "ascii":
        raise ValueError(f"breaks={chosen!r} needs decoded text, not bytes")
    return exact, chosen


def counts(text: str | bytes, *, breaks: Breaks = "ascii") -> dict[str, int]:
    r"""Count each line ending, treating CRLF as one ending rather than CR plus LF.

    The keys are the kinds of the chosen boundary set, always all present, in a fixed
    order: ``lf``, ``crlf``, ``cr``, then any others the set adds. Each call returns a new
    dict.

    >>> counts("a\r\nb\r\nc\n")
    {'lf': 1, 'crlf': 2, 'cr': 0}
    >>> counts(b"old\rmac\r")
    {'lf': 0, 'crlf': 0, 'cr': 2}
    >>> counts("page\x0cnext\u2028end", breaks="unicode")
    {'lf': 0, 'crlf': 0, 'cr': 0, 'vt': 0, 'ff': 1, 'nel': 0, 'ls': 1, 'ps': 0}
    """
    exact, chosen = checked(text, breaks)
    return tally(exact, chosen)


def detected_from(counted: Mapping[str, int]) -> Detected:
    present = [name for name, count in counted.items() if count]
    if not present:
        return "none"
    if len(present) == 1:
        return cast(Detected, present[0])
    return "mixed"


def detect(text: str | bytes, *, breaks: Breaks = "ascii") -> Detected:
    r"""Report the line-ending style: the single kind present, ``"mixed"`` or ``"none"``.

    >>> detect("a\r\nb\r\n"), detect(b"a\nb\r\n"), detect("one line")
    ('crlf', 'mixed', 'none')
    >>> detect("a\x85b"), detect("a\x85b", breaks="unicode")
    ('none', 'nel')
    """
    return detected_from(counts(text, breaks=breaks))


def convert(text: str | bytes, target: str, breaks: Breaks, keep_lone_cr: bool) -> str | bytes:
    """Normalize exact, checked input to the ending ``target``."""
    if isinstance(text, bytes):
        return bytes_pattern(keep_lone_cr).sub(target.encode("ascii"), text)
    return text_pattern(breaks, keep_lone_cr).sub(target, text)


def normalize(
    text: AnyStr, to: Style = "lf", *, breaks: Breaks = "ascii", keep_lone_cr: bool = False
) -> AnyStr:
    r"""Convert every line ending of the boundary set to the chosen style.

    A lone CR is converted too unless ``keep_lone_cr`` is true, which matches what git
    does for a path with the ``text`` attribute: only a CR that precedes an LF is part of
    an ending. ``bytes`` in, ``bytes`` out; a subclass comes back as the plain type.

    >>> normalize("a\r\nb\rc\n")
    'a\nb\nc\n'
    >>> normalize(b"a\nb\r\n", "crlf")
    b'a\r\nb\r\n'
    >>> normalize(b"a\rb\r\n", keep_lone_cr=True)
    b'a\rb\n'
    >>> normalize("one\x85two\u2029", breaks="unicode")
    'one\ntwo\n'
    """
    exact, chosen = checked(text, breaks)
    target = sequence(check_style(to))
    keep = flag("keep_lone_cr", keep_lone_cr)
    return cast(AnyStr, convert(exact, target, chosen, keep))
