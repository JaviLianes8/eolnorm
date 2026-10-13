"""Detect, normalize and count line endings in text or bytes."""

from __future__ import annotations

from typing import AnyStr, cast

from ._kinds import (
    BYTES_PATTERN,
    Breaks,
    Detected,
    Style,
    check_breaks,
    check_style,
    kinds,
    name_of,
    sequence,
    text_pattern,
)


def _check(text: object, breaks: object) -> Breaks:
    checked = check_breaks(breaks)
    if isinstance(text, bytes):
        if checked != "ascii":
            raise ValueError(f"breaks={checked!r} needs decoded text, not bytes")
    elif not isinstance(text, str):
        raise TypeError(f"expected str or bytes, got {type(text).__name__}")
    return checked


def counts(text: str | bytes, *, breaks: Breaks = "ascii") -> dict[str, int]:
    """Count each line ending, treating CRLF as one unit rather than CR plus LF.

    The keys are the kinds of the chosen boundary set, always all present, in a fixed
    order: ``lf``, ``crlf``, ``cr``, then any others the set adds.
    """
    breaks = _check(text, breaks)
    tally: dict[str, int] = dict.fromkeys(kinds(breaks), 0)
    if isinstance(text, bytes):
        for found in BYTES_PATTERN.finditer(text):
            tally[name_of(found.group().decode("ascii"))] += 1
    else:
        for match in text_pattern(breaks).finditer(text):
            tally[name_of(match.group())] += 1
    return tally


def detected_from(tally: dict[str, int]) -> Detected:
    present = [name for name, count in tally.items() if count]
    if not present:
        return "none"
    if len(present) == 1:
        return cast(Detected, present[0])
    return "mixed"


def detect(text: str | bytes, *, breaks: Breaks = "ascii") -> Detected:
    """Report the line-ending style: the single kind present, "mixed", or "none"."""
    return detected_from(counts(text, breaks=breaks))


def normalize(
    text: AnyStr, to: Style = "lf", *, breaks: Breaks = "ascii", keep_lone_cr: bool = False
) -> AnyStr:
    """Convert every line ending of the boundary set to the chosen style.

    A lone CR is converted too unless ``keep_lone_cr`` is true, which matches what git
    does for a path with the ``text`` attribute: only a CR that precedes an LF is part of
    an ending. ``bytes`` in, ``bytes`` out.
    """
    breaks = _check(text, breaks)
    target = sequence(check_style(to))
    if not isinstance(keep_lone_cr, bool):
        raise TypeError("keep_lone_cr must be a bool")
    if isinstance(text, bytes):
        raw = target.encode("ascii")
        if keep_lone_cr:
            return BYTES_PATTERN.sub(lambda m: m.group() if m.group() == b"\r" else raw, text)
        return BYTES_PATTERN.sub(raw, text)
    pattern = text_pattern(breaks)
    if keep_lone_cr:
        return pattern.sub(lambda m: m.group() if m.group() == "\r" else target, text)
    return pattern.sub(target, text)
