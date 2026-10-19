"""An independent implementation agrees: eolify (Rust) on the ASCII set, LF and CRLF.

Runs when ``pip install eolify`` is done (checked against 0.1.7); skipped otherwise.
"""

from __future__ import annotations

import io
import random

import pytest

from eolnorm import Normalizer, Style, normalize

eolify = pytest.importorskip("eolify")

PIECES = ["a", "\N{EURO SIGN}", " ", "\r\n", "\n", "\r", "\r\r\n", "\n\r", "\x85", "\x0c"]
MODES = {"lf": "LF", "crlf": "CRLF"}
STYLES: list[Style] = ["lf", "crlf"]


@pytest.mark.parametrize("style", STYLES)
def test_text_agrees_with_eolify(style: Style) -> None:
    mode = getattr(eolify.Mode, MODES[style])
    rng = random.Random(style)
    for _ in range(5000):
        text = "".join(rng.choice(PIECES) for _ in range(rng.randrange(0, 30)))
        assert normalize(text, style) == eolify.normalize_text(text, mode), repr(text)


@pytest.mark.parametrize("style", STYLES)
def test_streams_agree_with_eolify(style: Style) -> None:
    mode = getattr(eolify.Mode, MODES[style])
    rng = random.Random(style + "stream")
    for _ in range(1000):
        data = bytes(rng.choices(b"a\r\n\xff", k=rng.randrange(0, 40)))
        target = io.BytesIO()
        eolify.normalize_stream(io.BytesIO(data), target, mode)
        stream, out, start = Normalizer(style), b"", 0
        while start < len(data):
            end = start + rng.randrange(1, 6)
            out += stream.feed(data[start:end])
            start = end
        assert out + stream.feed(b"", final=True) == target.getvalue(), data
