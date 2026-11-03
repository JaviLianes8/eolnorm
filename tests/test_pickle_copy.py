"""Reports and streams pickle, copy and print as public eolnorm objects."""

from __future__ import annotations

import copy
import pickle
from pathlib import Path

import pytest

from eolnorm import FileReport, Normalizer, scan_file


def test_a_report_pickles_through_the_public_name(tmp_path: Path) -> None:
    path = tmp_path / "a.txt"
    path.write_bytes(b"a\r\nb\n")
    report = scan_file(path)
    for protocol in range(2, pickle.HIGHEST_PROTOCOL + 1):
        data = pickle.dumps(report, protocol=protocol)
        assert b"eolnorm._" not in data
        assert pickle.loads(data) == report


@pytest.mark.parametrize("protocol", range(2, pickle.HIGHEST_PROTOCOL + 1))
def test_a_stream_pickles_mid_way_with_its_held_cr(protocol: int) -> None:
    stream = Normalizer("crlf", keep_lone_cr=True)
    assert stream.feed(b"one\r") == b"one"
    data = pickle.dumps(stream, protocol=protocol)
    assert b"eolnorm._" not in data
    restored = pickle.loads(data)
    assert restored.feed(b"\ntwo\r", final=True) == b"\r\ntwo\r"
    assert restored.counts == {"lf": 0, "crlf": 1, "cr": 1}
    assert stream.feed(b"x", final=True) == b"\rx"


def test_a_copy_keeps_its_own_counts_and_held_cr() -> None:
    stream = Normalizer()
    stream.feed("a\r\nb\r")
    for twin in (copy.copy(stream), copy.deepcopy(stream)):
        assert twin.feed("\n") == "\n"
        assert twin.counts == {"lf": 0, "crlf": 2, "cr": 0}
    assert stream.counts == {"lf": 0, "crlf": 1, "cr": 0}
    assert stream.feed("", final=True) == "\n"
    assert stream.counts == {"lf": 0, "crlf": 1, "cr": 1}


def test_a_copy_keeps_the_stream_type() -> None:
    stream = Normalizer()
    stream.feed(b"a")
    twin = copy.copy(stream)
    with pytest.raises(TypeError, match="carries bytes"):
        twin.feed("b")


@pytest.mark.parametrize("to", ["lf", "crlf", "cr"])
@pytest.mark.parametrize("breaks", ["ascii", "unicode", "splitlines"])
@pytest.mark.parametrize("keep", [False, True])
def test_the_repr_shows_the_options_and_rebuilds_them(to: str, breaks: str, keep: bool) -> None:
    stream = Normalizer(to, breaks=breaks, keep_lone_cr=keep)  # type: ignore[arg-type]
    text = repr(stream)
    assert text == f"Normalizer({to!r}, breaks={breaks!r}, keep_lone_cr={keep!r})"
    rebuilt = eval(text, {"Normalizer": Normalizer})
    sample = "a\rb\r\nc\x85d\x1ee"
    assert rebuilt.feed(sample, final=True) == stream.feed(sample, final=True)


def test_a_report_repr_names_every_field() -> None:
    report = FileReport("p", True, None, False, {"lf": 0, "crlf": 0, "cr": 0}, "none", False)
    assert repr(report) == (
        "FileReport(path='p', binary=True, encoding=None, bom=False, "
        "counts={'lf': 0, 'crlf': 0, 'cr': 0}, detected='none', changed=False)"
    )


def test_reports_compare_by_every_field_and_hash_without_the_counts() -> None:
    def report(lf: int) -> FileReport:
        return FileReport("a", False, None, False, {"lf": lf, "crlf": 0, "cr": 0}, "lf")

    assert report(1) == report(1)
    assert report(1) != report(9)
    assert hash(report(1)) == hash(report(9))  # a dict cannot be hashed: counts take no part
    assert len({report(1), report(1)}) == 1
