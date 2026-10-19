"""Ground truth from git v2.54.0's convert.c and gitattributes documentation (fetched).

The statistics behind text=auto are read out of convert.c's gather_stats and
convert_is_binary (which control bytes are printable, DEL, the end-of-file byte, the shift)
and a port of those two functions is built from them; the CR and LF loops of crlf_to_git and
crlf_to_worktree are located in the source and ported the same way. The installed git is
checked separately in test_git.py.
"""

from __future__ import annotations

import random
import re
from collections.abc import Callable
from typing import NamedTuple

import pytest

from eolnorm import is_binary, normalize

Read = Callable[[str], str]


class Rules(NamedTuple):
    printable_controls: frozenset[int]
    delete: int
    below: int
    end_of_file: int
    shift: int


def _function(source: str, signature: str) -> str:
    start = source.index(signature)
    return source[start : source.index("\n}\n", start)]


def _char(literal: str) -> int:
    """The value of a C character literal such as '\\b', '\\033' or 'a'."""
    body = literal.strip("'")
    named = {"b": 8, "t": 9, "n": 10, "r": 13}
    if body.startswith(chr(92)):
        rest = body[1:]
        return int(rest, 8) if rest.isdigit() else named[rest]
    return ord(body)


def _rules(source: str) -> Rules:
    stats = _function(source, "static void gather_stats(")
    binary = _function(source, "static int convert_is_binary(")
    cases = re.search(r"/\* BS, HT, ESC and FF \*/\s*((?:case '[^']+':\s*)+)", stats)
    assert cases is not None
    printable = frozenset(_char(c) for c in re.findall(r"case ('[^']+'):", cases.group(1)))
    delete = re.search(r"if \(c == (\d+)\)\s*/\* DEL \*/", stats)
    below = re.search(r"else if \(c < (\d+)\)", stats)
    eof = re.search(r"buf\[size-1\] == ('[^']+')\)\s*stats->nonprintable--;", stats)
    shift = re.search(r"\(stats->printable >> (\d+)\) < stats->nonprintable", binary)
    assert delete and below and eof and shift
    assert "if (stats->lonecr)\n\t\treturn 1;" in binary
    assert "if (stats->nul)\n\t\treturn 1;" in binary
    values = (int(delete.group(1)), int(below.group(1)), _char(eof.group(1)), int(shift.group(1)))
    return Rules(printable, *values)


def _git_says_binary(data: bytes, rules: Rules) -> tuple[bool, bool]:
    """Port of gather_stats + convert_is_binary: (binary, binary without the lone CR rule)."""
    printable = nonprintable = nul = lonecr = 0
    index = 0
    while index < len(data):
        byte = data[index]
        index += 1
        if byte == 13:
            if index < len(data) and data[index] == 10:
                index += 1
            else:
                lonecr += 1
        elif byte == 10:
            pass
        elif byte == rules.delete:
            nonprintable += 1
        elif byte < rules.below:
            printable += byte in rules.printable_controls
            nul += byte == 0
            nonprintable += byte not in rules.printable_controls
        else:
            printable += 1
    if data and data[-1] == rules.end_of_file:
        nonprintable -= 1
    statistics = bool(nul) or (printable >> rules.shift) < nonprintable
    return bool(lonecr) or statistics, statistics


def test_the_statistics_are_read_from_convert_c(upstream: Read) -> None:
    rules = _rules(upstream("convert.c"))
    assert rules == Rules(frozenset({8, 9, 27, 12}), 127, 32, 26, 7)


def _samples(seed: int) -> list[bytes]:
    rng = random.Random(seed)
    pieces = [b"a", b"\r\n", b"\n", b"\r", b"\x00", b"\x1a", b"\x7f", b"\x80", b"\xff"]
    pieces += [bytes([b]) for b in range(32)] + [b"a" * 63, b"a" * 127]
    out = [b"a" * n + b"\x01" * k for n in range(120, 140) for k in (1, 2)]
    out += [b"a" * n + b"\x1a" for n in range(5)] + [b"\x1a" * 2, b"\x1a", b""]
    return out + [b"".join(rng.choices(pieces, k=rng.randrange(1, 40))) for _ in range(20000)]


def test_is_binary_is_the_ported_statistics_except_for_lone_cr(upstream: Read) -> None:
    rules = _rules(upstream("convert.c"))
    for sample in _samples(7):
        git_binary, without_cr_rule = _git_says_binary(sample, rules)
        assert is_binary(sample) == without_cr_rule, sample
        if b"\r" not in sample.replace(b"\r\n", b""):
            assert is_binary(sample) == git_binary, sample


def test_the_crlf_loops_in_convert_c_are_keep_lone_cr(upstream: Read) -> None:
    source = upstream("convert.c")
    checkin = _function(source, "static int crlf_to_git(")
    checkout = _function(source, "static int crlf_to_worktree(")
    assert "if (! (c == '\\r' && (1 < len && *src == '\\n')))" in checkin
    assert "if (nl > src && nl[-1] == '\\r') {" in checkout
    rng = random.Random(54)
    for _ in range(5000):
        data = bytes(rng.choices(b"a\r\n", k=rng.randrange(0, 20)))
        dropped = bytes(
            b for i, b in enumerate(data) if not (b == 13 and data[i + 1 : i + 2] == b"\n")
        )
        assert normalize(data, "lf", keep_lone_cr=True) == dropped, data
        added = re.sub(rb"(?<!\r)\n", b"\r\n", data)
        assert normalize(data, "crlf", keep_lone_cr=True) == added, data


@pytest.mark.parametrize(
    "sentence",
    [
        "the file's line endings are normalized to LF in the index",
        "converts the file's line endings in the working directory to CRLF when the file is "
        "checked out",
        'When `text` is set to "auto", Git decides by itself whether the file is text or binary',
    ],
)
def test_the_documented_attribute_semantics(upstream: Read, sentence: str) -> None:
    assert sentence in re.sub(r"\s+", " ", upstream("gitattributes.adoc"))
