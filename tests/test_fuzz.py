"""Seeded fuzzing: random and hostile input never crashes, hangs or grows faster than linear."""

from __future__ import annotations

import random
import re
import time
from collections.abc import Callable
from pathlib import Path
from typing import get_args

import pytest

from eolnorm import (
    Breaks,
    Normalizer,
    Style,
    counts,
    detect,
    is_binary,
    normalize,
    normalize_file,
    scan_file,
)

SETS: tuple[Breaks, ...] = get_args(Breaks)
STYLES: tuple[Style, ...] = get_args(Style)
PIECES = ["a", "\N{EURO SIGN}", "\N{GRINNING FACE}", " ", "\t", "\x00", "\x1a", "\x7f"]
PIECES += ["\r\n", "\n", "\r", "\r\r\n", "\n\r", "\x0b", "\x0c", "\x1c", "\x1d", "\x1e"]
PIECES += ["\x85", "\N{LINE SEPARATOR}", "\N{PARAGRAPH SEPARATOR}", "\ufeff", "\udcff"]
CODECS = [None, "utf-8", "utf-8-sig", "latin-1", "cp1252", "utf-16", "utf-16-le", "utf-32-be"]
CODECS += ["shift_jis", "utf-7", "ascii"]


def _text(rng: random.Random, size: int = 24) -> str:
    return "".join(rng.choice(PIECES) for _ in range(rng.randrange(0, size)))


def _bytes(rng: random.Random) -> bytes:
    marks = [b"", b"\xef\xbb\xbf", b"\xff\xfe", b"\xfe\xff", b"\xff\xfe\x00\x00"]
    body = bytes(rng.choices(b"a\r\n\x00\x1a\x80\xff\x0b", k=rng.randrange(0, 30)))
    return rng.choice(marks) + body


def test_random_text_keeps_its_endings_and_converts_all_of_them() -> None:
    rng = random.Random(1)
    for _ in range(4000):
        text, breaks, to = _text(rng), rng.choice(SETS), rng.choice(STYLES)
        before = sum(counts(text, breaks=breaks).values())
        out = normalize(text, to, breaks=breaks)
        after = counts(out, breaks=breaks)
        assert sum(after.values()) == before, repr(text)
        assert detect(out, breaks=breaks) == (to if before else "none"), repr(text)
        assert normalize(out, to, breaks=breaks) == out, repr(text)
        assert normalize(out, "lf", breaks=breaks) == normalize(text, "lf", breaks=breaks)


def test_bytes_and_text_agree_on_the_ascii_set() -> None:
    rng = random.Random(2)
    for _ in range(4000):
        text = _text(rng).encode("utf-8", "surrogatepass").decode("utf-8", "surrogateescape")
        data = text.encode("utf-8", "surrogateescape")
        to, keep = rng.choice(STYLES), rng.random() < 0.5
        assert normalize(data, to, keep_lone_cr=keep) == normalize(
            text, to, keep_lone_cr=keep
        ).encode("utf-8", "surrogateescape")
        assert counts(data) == counts(text)


def test_keep_lone_cr_touches_only_the_real_endings() -> None:
    # Hide each lone CR behind a mark, convert without the option, then put the CRs back.
    rng = random.Random(3)
    for _ in range(4000):
        text, breaks, to = _text(rng), rng.choice(SETS), rng.choice(STYLES)
        hidden = re.sub(r"\r(?!\n)", "#", text)
        expected = normalize(hidden, to, breaks=breaks).replace("#", "\r")
        assert normalize(text, to, breaks=breaks, keep_lone_cr=True) == expected, repr(text)


def test_any_split_of_random_bytes_streams_like_one_call() -> None:
    rng = random.Random(4)
    for _ in range(2000):
        data, to, keep = _bytes(rng), rng.choice(STYLES), rng.random() < 0.5
        stream, out, start = Normalizer(to, keep_lone_cr=keep), b"", 0
        while start < len(data):
            end = start + rng.randrange(0, 5)
            out += stream.feed(data[start:end])
            start = end
        out += stream.feed(b"", final=True)
        assert out == normalize(data, to, keep_lone_cr=keep), data
        assert stream.counts == counts(data)


def test_random_files_either_normalize_cleanly_or_stay_untouched(tmp_path: Path) -> None:
    rng = random.Random(5)
    path = tmp_path / "f.txt"
    for _ in range(1500):
        data, codec = _bytes(rng), rng.choice(CODECS)
        breaks, to = rng.choice(SETS), rng.choice(STYLES)
        path.write_bytes(data)
        try:
            report = normalize_file(path, to, breaks=breaks, encoding=codec)
        except ValueError:  # UnicodeDecodeError included: a codec that does not fit
            assert path.read_bytes() == data
            continue
        if report.binary:
            assert path.read_bytes() == data and not any(report.counts.values())
            continue
        again = scan_file(path, breaks=breaks, encoding=codec)
        assert again.detected in (to, "none") or again.binary, (data, codec, breaks, to)
        assert sum(again.counts.values()) == sum(report.counts.values())


HOSTILE: list[object] = [None, 0, 1.5, b"lf", bytearray(b"a"), memoryview(b"a"), ["lf"], {}]
HOSTILE += [object(), "x" * 100_000, "\x00", "\udcff", "LF", " lf"]


@pytest.mark.parametrize("value", HOSTILE, ids=range(len(HOSTILE)))
def test_hostile_arguments_raise_short_typed_errors(value: object, tmp_path: Path) -> None:
    path = tmp_path / "f.txt"
    path.write_bytes(b"a\r\n")
    calls: list[Callable[[], object]] = [
        lambda: normalize("a", value),  # type: ignore[arg-type]
        lambda: counts("a", breaks=value),  # type: ignore[arg-type]
        lambda: Normalizer(value),  # type: ignore[arg-type]
        lambda: normalize_file(path, encoding=value, dry_run=True),  # type: ignore[arg-type]
        lambda: scan_file(value),  # type: ignore[arg-type]
        lambda: is_binary(value),  # type: ignore[arg-type]
    ]
    for call in calls:
        try:
            call()
        except (TypeError, ValueError) as error:
            assert len(str(error)) < 200
        except OSError:  # the operating system's own message about a path it refused
            pass
    assert path.read_bytes() == b"a\r\n"


def _seconds(action: Callable[[], object]) -> float:
    best = float("inf")
    for _ in range(3):
        start = time.perf_counter()
        action()
        best = min(best, time.perf_counter() - start)
    return best


def _feed_one_by_one(data: bytes) -> None:
    stream = Normalizer("crlf")
    for index in range(len(data)):
        stream.feed(data[index : index + 1])
    stream.feed(b"", final=True)


ADVERSARIAL = ["\r", "\r\n", "\r\r\n", "\n\r", "\x85\N{LINE SEPARATOR}", "a\r\x00"]


@pytest.mark.parametrize("unit", ADVERSARIAL)
def test_the_work_grows_linearly_with_the_input(unit: str) -> None:
    def run(times: int) -> float:
        text = unit * times
        data = text.encode("utf-8")

        def work() -> None:
            normalize(text, "crlf", breaks="splitlines")
            normalize(text, "lf", keep_lone_cr=True)
            counts(text, breaks="unicode")
            is_binary(data)
            normalize(data, "cr")

        return _seconds(work)

    small, large = run(20_000), run(320_000)
    # Sixteen times the input: linear work takes about sixteen times as long.
    assert large < 80 * max(small, 1e-4), (small, large)


def test_a_stream_of_one_byte_chunks_is_linear() -> None:
    small = _seconds(lambda: _feed_one_by_one(b"\r" * 4_000))
    large = _seconds(lambda: _feed_one_by_one(b"\r" * 64_000))
    assert large < 80 * max(small, 1e-4), (small, large)
