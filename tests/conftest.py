"""Shared fixtures: the fetched third-party sources and the boundary sets as code points."""

from __future__ import annotations

import functools
import hashlib
import json
import sys
from collections.abc import Callable
from pathlib import Path

import pytest

from eolnorm import Breaks, normalize

UPSTREAM = Path(__file__).parent / "upstream"


def read_upstream(name: str) -> str:
    """A source fetched by scripts/fetch_upstream.py; skip when absent, fail when altered."""
    entry = json.loads((UPSTREAM / "MANIFEST.json").read_text(encoding="utf-8"))[name]
    path = UPSTREAM / name
    if not path.exists():
        pytest.skip(f"{name} is not fetched: run scripts/fetch_upstream.py")
    data = path.read_bytes()
    assert len(data) == entry["size"], f"{name} is not the recorded file"
    assert hashlib.sha256(data).hexdigest() == entry["sha256"], f"{name} is not the recorded file"
    return data.decode("utf-8")


@functools.cache
def breaking_points(breaks: Breaks) -> frozenset[int]:
    """Every code point the set treats as an ending, found by converting all of Unicode.

    One call over every code point, each followed by "a" (not an ending in any set): a
    code point is an ending exactly when normalizing to CRLF turns it into CRLF.
    """
    points = [p for p in range(sys.maxunicode + 1) if not 0xD800 <= p <= 0xDFFF and p != 0x61]
    pieces = normalize("a".join(map(chr, points)), "crlf", breaks=breaks).split("a")
    return frozenset(p for p, piece in zip(points, pieces, strict=True) if piece == "\r\n")


@pytest.fixture
def upstream() -> Callable[[str], str]:
    return read_upstream


@pytest.fixture
def breaking() -> Callable[[Breaks], frozenset[int]]:
    return breaking_points
