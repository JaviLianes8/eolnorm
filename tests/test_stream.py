"""Normalizer: chunk borders never change the result or the counts."""

from __future__ import annotations

import itertools
import random

import pytest

from eolnorm import Normalizer, counts, normalize

PIECES = ["a", "\r\n", "\r", "\n", "\x85", "\u2028", "\x0c", "b\r"]


def _split(text: str, rng: random.Random) -> list[str]:
    cuts = sorted(rng.sample(range(len(text) + 1), k=min(len(text) + 1, rng.randrange(0, 6))))
    edges = [0, *cuts, len(text)]
    return [text[start:end] for start, end in itertools.pairwise(edges)]


@pytest.mark.parametrize("breaks", ["ascii", "unicode"])
@pytest.mark.parametrize("to", ["lf", "crlf", "cr"])
@pytest.mark.parametrize("keep", [False, True])
def test_any_chunking_gives_the_one_shot_result(breaks: str, to: str, keep: bool) -> None:
    rng = random.Random(f"{breaks}{to}{keep}")
    for _ in range(400):
        text = "".join(rng.choice(PIECES) for _ in range(rng.randrange(0, 12)))
        stream = Normalizer(to, breaks=breaks, keep_lone_cr=keep)  # type: ignore[arg-type]
        chunks = _split(text, rng)
        out = "".join(stream.feed(chunk) for chunk in chunks) + stream.feed("", final=True)
        expected = normalize(text, to, breaks=breaks, keep_lone_cr=keep)  # type: ignore[arg-type]
        assert out == expected, (text, chunks)
        assert stream.counts == counts(text, breaks=breaks), (text, chunks)  # type: ignore[arg-type]


def test_crlf_split_across_chunks_is_one_ending() -> None:
    stream = Normalizer("lf")
    assert stream.feed(b"one\r") == b"one"
    assert stream.counts == {"lf": 0, "crlf": 0, "cr": 0}
    assert stream.feed(b"\ntwo") == b"\ntwo"
    assert stream.counts == {"lf": 0, "crlf": 1, "cr": 0}
    assert stream.detected == "crlf"


def test_final_releases_a_held_cr() -> None:
    stream = Normalizer("crlf")
    assert stream.feed("end\r") == "end"
    assert stream.feed("", final=True) == "\r\n"
    assert stream.counts["cr"] == 1


def test_final_keeps_a_held_lone_cr_when_asked() -> None:
    stream = Normalizer("lf", keep_lone_cr=True)
    assert stream.feed(b"x\r") + stream.feed(b"", final=True) == b"x\r"


def test_a_lone_cr_chunk_is_held_until_the_next_one() -> None:
    stream = Normalizer("lf")
    assert [stream.feed(chunk) for chunk in ["\r", "\r", "\n"]] == ["", "\n", "\n"]
    assert stream.counts == {"lf": 0, "crlf": 1, "cr": 1}


def test_detected_before_any_input_is_none() -> None:
    assert Normalizer().detected == "none"
    assert Normalizer(breaks="splitlines").counts["rs"] == 0


def test_mixing_str_and_bytes_is_rejected() -> None:
    stream = Normalizer()
    stream.feed("a\r")
    with pytest.raises(TypeError, match="mix"):
        stream.feed(b"\n")


def test_a_str_subclass_does_not_lock_out_plain_str() -> None:
    class Text(str):
        pass

    stream = Normalizer()
    assert stream.feed(Text("a\r")) == "a"
    assert stream.feed("\n") == "\n"


def test_bad_arguments_are_rejected() -> None:
    with pytest.raises(TypeError):
        Normalizer().feed(bytearray(b"a"))  # type: ignore[type-var]
    with pytest.raises(ValueError, match="style"):
        Normalizer("lfcr")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="boundary set"):
        Normalizer(breaks="every")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        Normalizer(keep_lone_cr="yes")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="decoded text"):
        Normalizer(breaks="unicode").feed(b"a")


def test_counts_property_is_a_copy() -> None:
    stream = Normalizer()
    stream.counts["lf"] = 99
    assert stream.counts["lf"] == 0
