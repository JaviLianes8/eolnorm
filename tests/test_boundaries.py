"""The boundary sets agree with their ground truth: the interpreter and the UCD data."""

from __future__ import annotations

import random
import sys
from pathlib import Path

import pytest

from eolnorm import Breaks, counts, normalize

CRLF = chr(13) + chr(10)
LINEBREAK = Path(__file__).parent / "upstream" / "LineBreak.txt"

# One character of every set, plus CRLF and ordinary characters, to build random texts.
ALPHABET = ["a", "b", " ", "\r\n", "\n", "\r", "\x0b", "\x0c", "\x1c", "\x1d", "\x1e"]
ALPHABET += ["\x85", "\u2028", "\u2029", "\x1f", "\x84", "\u2027", "\u202a", "\t"]


def _breaking(breaks: Breaks) -> set[int]:
    # One call over every code point, each followed by "a" (not a break): a code point is a
    # break exactly when normalizing to CRLF turns it into CRLF.
    points = [p for p in range(sys.maxunicode + 1) if not 0xD800 <= p <= 0xDFFF and p != 0x61]
    pieces = normalize("a".join(map(chr, points)), "crlf", breaks=breaks).split("a")
    return {p for p, piece in zip(points, pieces, strict=True) if piece == CRLF}


def test_the_separator_used_above_is_not_a_break() -> None:
    assert sum(counts("a", breaks="splitlines").values()) == 0


def test_splitlines_set_is_what_the_interpreter_splits_on() -> None:
    # Every code point, asked of the running interpreter, not of the documentation.
    expected = {
        point
        for point in range(sys.maxunicode + 1)
        if not 0xD800 <= point <= 0xDFFF and len(f"a{chr(point)}b".splitlines()) == 2
    }
    assert _breaking("splitlines") == expected


def test_splitlines_set_matches_the_documented_table() -> None:
    # https://docs.python.org/3/library/stdtypes.html#str.splitlines (fetched 2026-10-13)
    documented = {0x0A, 0x0D, 0x0B, 0x0C, 0x1C, 0x1D, 0x1E, 0x85, 0x2028, 0x2029}
    assert _breaking("splitlines") == documented


def test_ascii_set_is_cr_and_lf() -> None:
    assert _breaking("ascii") == {0x0A, 0x0D}


@pytest.mark.skipif(not LINEBREAK.exists(), reason="run scripts/fetch_upstream.py")
def test_unicode_set_is_the_uax14_mandatory_breaks() -> None:
    # Classes BK, CR, LF and NL in LineBreak.txt are the mandatory breaks (UAX #14 LB4, LB5).
    mandatory: set[int] = set()
    for line in LINEBREAK.read_text(encoding="utf-8").splitlines():
        fields = line.split("#", 1)[0].split(";")
        if len(fields) != 2 or fields[1].strip() not in {"BK", "CR", "LF", "NL"}:
            continue
        first, _, last = fields[0].strip().partition("..")
        mandatory.update(range(int(first, 16), int(last or first, 16) + 1))
    assert len(mandatory) == 7
    assert _breaking("unicode") == mandatory


def test_unicode_set_is_the_derived_mandatory_breaks() -> None:
    # Derived from LineBreak.txt 18.0.0: BK is 000B..000C, 2028 and 2029; CR, LF and NL
    # (0085) are one code point each.
    assert _breaking("unicode") == {0x0A, 0x0B, 0x0C, 0x0D, 0x85, 0x2028, 0x2029}


def test_normalize_agrees_with_splitlines_on_random_text() -> None:
    rng = random.Random(14)
    for _ in range(3000):
        text = "".join(rng.choice(ALPHABET) for _ in range(rng.randrange(0, 14)))
        kept = text.splitlines(keepends=True)
        bare = text.splitlines()
        expected = "".join(b if k == b else b + "\n" for k, b in zip(kept, bare, strict=True))
        assert normalize(text, "lf", breaks="splitlines") == expected, repr(text)
        ended = sum(k != b for k, b in zip(kept, bare, strict=True))
        assert sum(counts(text, breaks="splitlines").values()) == ended, repr(text)
