"""Subclasses of str and bytes are read through the base type; impostors are refused."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import pytest

from eolnorm import Normalizer, counts, detect, is_binary, normalize, normalize_file, scan_file


def _hostile(base: type) -> Any:
    """A subclass whose every relevant method lies."""

    def lie(*args: object, **kwargs: object) -> object:
        raise AssertionError("a method of the subclass ran")

    names = ["__add__", "__radd__", "__getitem__", "__len__", "__iter__", "__contains__"]
    names += ["count", "endswith", "startswith", "replace", "translate", "split", "encode"]
    names += ["decode", "__str__", "__bytes__", "__buffer__", "__eq__", "__hash__", "find"]
    return type("Hostile", (base,), {name: lie for name in names if hasattr(base, name)})


TEXT = "a\r\nb\rc\nd\x85e\u2028f"
DATA = b"a\r\nb\rc\nd\x00"


def test_text_functions_read_a_str_subclass_as_plain_str() -> None:
    hostile = _hostile(str)(TEXT)
    for breaks in ("ascii", "unicode", "splitlines"):
        assert counts(hostile, breaks=breaks) == counts(TEXT, breaks=breaks)
        assert detect(hostile, breaks=breaks) == detect(TEXT, breaks=breaks)
        result = normalize(hostile, "crlf", breaks=breaks)
        assert type(result) is str
        assert result == normalize(TEXT, "crlf", breaks=breaks)


def test_bytes_functions_read_a_bytes_subclass_as_plain_bytes() -> None:
    hostile = _hostile(bytes)(DATA)
    assert counts(hostile) == counts(DATA)
    result = normalize(hostile, "cr", keep_lone_cr=True)
    assert type(result) is bytes
    assert result == normalize(DATA, "cr", keep_lone_cr=True)
    assert is_binary(hostile) is True
    assert is_binary(_hostile(bytes)(b"plain\r\n")) is False


def test_a_stream_reads_subclass_chunks_as_their_base_type() -> None:
    stream = Normalizer()
    first = stream.feed(_hostile(str)("a\r"))
    second = stream.feed(_hostile(str)("\nb"), final=True)
    assert (type(first), type(second), first + second) == (str, str, "a\nb")
    data_stream = Normalizer("crlf")
    out = data_stream.feed(_hostile(bytes)(b"x\n"), final=True)
    assert (type(out), out) == (bytes, b"x\r\n")


def test_option_strings_may_be_str_subclasses() -> None:
    class Option(str):
        pass

    assert normalize("a\nb", Option("crlf"), breaks=Option("unicode")) == "a\r\nb"  # type: ignore[arg-type]
    assert repr(Normalizer(Option("cr"))) == "Normalizer('cr', breaks='ascii', keep_lone_cr=False)"  # type: ignore[arg-type]


def test_objects_that_only_claim_to_be_strings_are_refused() -> None:
    class Impostor:
        __class__ = str  # type: ignore[assignment]

    assert isinstance(Impostor(), str)
    for call in (
        lambda: normalize(Impostor()),  # type: ignore[type-var]
        lambda: counts(Impostor()),  # type: ignore[arg-type]
        lambda: is_binary(Impostor()),  # type: ignore[arg-type]
        lambda: normalize("a", Impostor()),  # type: ignore[arg-type]
        lambda: Normalizer().feed(Impostor()),  # type: ignore[type-var]
    ):
        with pytest.raises(TypeError):
            call()


def test_bool_flags_refuse_truthy_and_falsy_values_of_other_types() -> None:
    for value in (1, 0, "yes", None, 1.0, [True]):
        with pytest.raises(TypeError, match="must be a bool"):
            normalize("a", keep_lone_cr=value)  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="must be a bool"):
            Normalizer().feed("a", value)  # type: ignore[arg-type]


def test_a_path_like_returning_a_str_subclass_reports_a_plain_str(tmp_path: Path) -> None:
    target = tmp_path / "a.txt"
    target.write_bytes(b"a\r\n")

    class Name(str):
        pass

    class Where:
        def __fspath__(self) -> str:
            return Name(str(target))

    report = normalize_file(Where(), dry_run=True)
    assert type(report.path) is str
    assert report.path == str(target) and report.changed


def test_a_path_like_returning_bytes_is_refused(tmp_path: Path) -> None:
    class Where:
        def __fspath__(self) -> bytes:
            return os.fsencode(tmp_path / "a.txt")

    with pytest.raises(TypeError, match=r"os\.PathLike"):
        scan_file(Where())  # type: ignore[arg-type]


@pytest.mark.skipif(sys.version_info < (3, 12), reason="the buffer protocol in Python")
def test_a_buffer_override_cannot_change_what_is_read() -> None:
    class Shadow(bytes):
        def __buffer__(self, flags: int) -> memoryview:
            return memoryview(b"\x00\x00\x00\x00")

    data = Shadow(b"a\r\nb\n")
    assert (is_binary(data), counts(data), normalize(data)) == (
        *(False, {"lf": 1, "crlf": 1, "cr": 0}),
        b"a\nb\n",
    )
