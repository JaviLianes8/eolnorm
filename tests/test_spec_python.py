"""Ground truth from the CPython v3.14.0 documentation, read from the fetched pages.

Sources (tests/upstream/MANIFEST.json, fetched 2026-10-18): Doc/library/stdtypes.rst (the
str.splitlines table), Doc/glossary.rst (universal newlines), Doc/library/io.rst and
Doc/library/functions.rst (the newline argument). Each claim is cut from the page text and
checked against eolnorm and against the running interpreter's own io machinery.
"""

from __future__ import annotations

import codecs
import io
import random
import re
from collections.abc import Callable

import pytest

from eolnorm import Breaks, Style, counts, normalize

Read = Callable[[str], str]
PIECES = ["a", "\N{LATIN SMALL LETTER E WITH ACUTE}", " ", "\r\n", "\n", "\r", "\r\r\n", "\n\r"]
PIECES += ["\x0b", "\x0c", "\x1e", "\x85", "\N{LINE SEPARATOR}", "\N{PARAGRAPH SEPARATOR}"]


def _literals(text: str, pattern: str) -> list[str]:
    """The Python string literals the page writes in double backquotes, decoded."""
    return [codecs.decode(raw, "unicode_escape") for raw in re.findall(pattern, text)]


def test_the_splitlines_table_is_the_splitlines_set(
    upstream: Read, breaking: Callable[[Breaks], frozenset[int]]
) -> None:
    section = upstream("stdtypes.rst").split(".. method:: str.splitlines", 1)[1]
    table = section.split(".. versionchanged::", 1)[0]
    rows = re.findall(r"^   \| ``([^`]+)``(?: or ``([^`]+)``)? +\|", table, flags=re.MULTILINE)
    boundaries = {codecs.decode(raw, "unicode_escape") for row in rows for raw in row if raw}
    assert len(rows) == 11 and "\r\n" in boundaries
    singles = {char for char in boundaries if len(char) == 1}
    assert breaking("splitlines") == {ord(char) for char in singles}
    assert counts("\r\n", breaks="splitlines")["crlf"] == 1
    for char in singles:
        assert normalize(f"a{char}b", "crlf", breaks="splitlines") == "a\r\nb"


def test_the_glossary_universal_newlines_are_the_ascii_set(
    upstream: Read, breaking: Callable[[Breaks], frozenset[int]]
) -> None:
    glossary = upstream("glossary.rst")
    entry = glossary.split("\n   universal newlines\n", 1)[1].split("\n\n", 1)[0]
    conventions = _literals(entry, r"``'([^']+)'``")
    assert sorted(conventions) == sorted(["\n", "\r\n", "\r"])
    assert breaking("ascii") == {ord(char) for char in conventions if len(char) == 1}
    for ending in conventions:
        assert normalize(ending) == "\n"
        assert sum(counts(ending).values()) == 1


def _newline_sentence(page: str) -> list[str]:
    flat = re.sub(r"\s+", " ", page)
    found = re.search(
        r"Lines in the input can end in (.+?), and these are translated into ``'(.+?)'``", flat
    )
    assert found is not None
    assert codecs.decode(found.group(2), "unicode_escape") == "\n"
    return _literals(found.group(1), r"``'([^']+)'``")


@pytest.mark.parametrize("page", ["io.rst", "functions.rst"])
def test_reading_in_universal_newlines_mode_is_normalize_to_lf(upstream: Read, page: str) -> None:
    assert sorted(_newline_sentence(upstream(page))) == sorted(["\n", "\r", "\r\n"])
    rng = random.Random(page)
    for _ in range(3000):
        text = "".join(rng.choice(PIECES) for _ in range(rng.randrange(0, 16)))
        raw = io.BytesIO(text.encode("utf-8"))
        read = io.TextIOWrapper(raw, encoding="utf-8", newline=None).read()
        assert read == normalize(text, "lf"), repr(text)


def test_the_io_line_splitter_finds_the_endings_counts_finds() -> None:
    rng = random.Random(278)
    for _ in range(3000):
        text = "".join(rng.choice(PIECES) for _ in range(rng.randrange(0, 16)))
        lines = io.StringIO(text, newline="").readlines()
        assert "".join(lines) == text
        tally = {"lf": 0, "crlf": 0, "cr": 0}
        for line in lines:
            if line.endswith("\r\n"):
                tally["crlf"] += 1
            elif line.endswith("\n"):
                tally["lf"] += 1
            elif line.endswith("\r"):
                tally["cr"] += 1
        assert counts(text) == tally, repr(text)


@pytest.mark.parametrize("newline", ["\r\n", "\r"])
def test_writing_lf_text_with_a_newline_is_normalize(newline: str) -> None:
    rng = random.Random(newline)
    for _ in range(2000):
        text = normalize("".join(rng.choice(PIECES) for _ in range(rng.randrange(0, 16))))
        out = io.BytesIO()
        with io.TextIOWrapper(out, encoding="utf-8", newline=newline, write_through=True) as f:
            f.write(text)
            data = out.getvalue()
        style: Style = "crlf" if newline == "\r\n" else "cr"
        assert data.decode("utf-8") == normalize(text, style), repr(text)
