"""The boundary sets agree with their ground truth: the interpreter and the UCD data."""

from __future__ import annotations

import random
import re
import sys
from collections.abc import Callable

from eolnorm import Breaks, counts, normalize

Breaking = Callable[[Breaks], frozenset[int]]

# One character of every set, plus CRLF and ordinary characters, to build random texts.
ALPHABET = ["a", "b", " ", "\r\n", "\n", "\r", "\x0b", "\x0c", "\x1c", "\x1d", "\x1e"]
ALPHABET += ["\x85", "\N{LINE SEPARATOR}", "\N{PARAGRAPH SEPARATOR}", "\x1f", "\x84", "\t"]
ALPHABET += ["\N{HYPHENATION POINT}", "\N{LEFT-TO-RIGHT EMBEDDING}"]


def test_the_separator_used_by_the_scan_is_not_a_break() -> None:
    sets: tuple[Breaks, ...] = ("ascii", "unicode", "splitlines")
    for breaks in sets:
        assert sum(counts("a", breaks=breaks).values()) == 0


def test_splitlines_set_is_what_the_interpreter_splits_on(breaking: Breaking) -> None:
    # Every code point, asked of the running interpreter, not of the documentation.
    expected = {
        point
        for point in range(sys.maxunicode + 1)
        if not 0xD800 <= point <= 0xDFFF and len(f"a{chr(point)}b".splitlines()) == 2
    }
    assert breaking("splitlines") == expected


def test_ascii_set_is_cr_and_lf(breaking: Breaking) -> None:
    assert breaking("ascii") == {0x0A, 0x0D}


def test_unicode_set_is_the_uax14_mandatory_breaks(
    breaking: Breaking, upstream: Callable[[str], str]
) -> None:
    # The classes LB4 and LB5 of UAX #14 always break after, then their code points in
    # LineBreak.txt: both read from the fetched files.
    report = upstream("tr14-57.html")
    rules = report[report.index('name="LB4"') : report.index('name="LB6"')]
    classes = set(re.findall(r'<p style="text-align:center">([A-Z]{2}) !</p>', rules))
    assert classes == {"BK", "CR", "LF", "NL"}
    assert '<p style="text-align:center">CR \N{MULTIPLICATION SIGN} LF</p>' in rules
    mandatory: set[int] = set()
    for line in upstream("LineBreak.txt").splitlines():
        fields = line.split("#", 1)[0].split(";")
        if len(fields) != 2 or fields[1].strip() not in classes:
            continue
        first, _, last = fields[0].strip().partition("..")
        mandatory.update(range(int(first, 16), int(last or first, 16) + 1))
    assert len(mandatory) == 7
    assert breaking("unicode") == mandatory


def test_unicode_set_is_the_derived_mandatory_breaks(breaking: Breaking) -> None:
    # Written by hand from LineBreak.txt 18.0.0 (the test above reads the file itself): BK
    # is 000B..000C, 2028 and 2029; CR, LF and NL (0085) are one code point each.
    assert breaking("unicode") == {0x0A, 0x0B, 0x0C, 0x0D, 0x85, 0x2028, 0x2029}


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
