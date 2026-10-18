"""Errors are typed, raised before any work, and their messages stay small whatever the input."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from eolnorm import Normalizer, counts, detect, is_binary, normalize, normalize_file, scan_file

HUGE = "x" * 1_000_000
# Every message names at most 40 characters of a value or a type name, plus fixed words.
BOUND = 120


def _raises(kind: type[BaseException], call: Callable[[], object]) -> str:
    with pytest.raises(kind) as raised:
        call()
    message = str(raised.value)
    assert len(message) <= BOUND, message[:200]
    return message


def test_unknown_values_are_value_errors_quoting_forty_characters() -> None:
    for call in (
        lambda: normalize("a", HUGE),  # type: ignore[arg-type]
        lambda: counts("a", breaks=HUGE),  # type: ignore[arg-type]
        lambda: Normalizer(HUGE),  # type: ignore[arg-type]
        lambda: Normalizer(breaks=HUGE),  # type: ignore[arg-type]
    ):
        message = _raises(ValueError, call)
        assert message.endswith(repr("x" * 40) + "..."), message


def test_short_unknown_values_are_quoted_whole() -> None:
    assert _raises(ValueError, lambda: normalize("a", "LF")) == "unknown style: 'LF'"  # type: ignore[arg-type]
    message = _raises(ValueError, lambda: detect("a", breaks="all"))  # type: ignore[arg-type]
    assert message == "unknown boundary set: 'all'"


def test_options_of_the_wrong_type_are_type_errors() -> None:
    cases: list[tuple[Callable[[], object], str]] = [
        (lambda: normalize("a", 5), "style must be a str, got int"),  # type: ignore[arg-type]
        (lambda: detect("a", breaks=None), "boundary set must be a str, got NoneType"),  # type: ignore[arg-type]
        (lambda: normalize("a", b"lf"), "style must be a str, got bytes"),  # type: ignore[arg-type]
        (lambda: normalize("a", keep_lone_cr=1), "keep_lone_cr must be a bool, got int"),  # type: ignore[arg-type]
        (lambda: Normalizer().feed("a", 1), "final must be a bool, got int"),  # type: ignore[arg-type]
        (lambda: Normalizer(keep_lone_cr="no"), "keep_lone_cr must be a bool, got str"),  # type: ignore[arg-type]
        (lambda: counts(3.5), "expected str or bytes, got float"),  # type: ignore[arg-type]
        (lambda: is_binary("a"), "expected bytes, got str"),  # type: ignore[arg-type]
        (lambda: scan_file(7), "path must be a str or os.PathLike[str], got int"),  # type: ignore[arg-type]
        (lambda: scan_file(b"a"), "path must be a str or os.PathLike[str], got bytes"),  # type: ignore[arg-type]
    ]
    for call, message in cases:
        assert _raises(TypeError, call) == message


def test_file_options_are_checked_before_the_path_is_read(tmp_path: Path) -> None:
    missing = tmp_path / "missing"
    assert _raises(TypeError, lambda: normalize_file(missing, dry_run="no")) == (  # type: ignore[arg-type]
        "dry_run must be a bool, got str"
    )
    message = _raises(TypeError, lambda: scan_file(missing, encoding=b"utf-8"))  # type: ignore[arg-type]
    assert message == "encoding must be a str or None, got bytes"
    assert _raises(ValueError, lambda: normalize_file(missing, encoding=HUGE)).endswith("...")


@pytest.mark.parametrize("name", ["hex", "base64", "rot13", "zlib", "bz2", "uu", "quopri"])
def test_codecs_that_are_not_text_encodings_are_refused(tmp_path: Path, name: str) -> None:
    path = tmp_path / "a.txt"
    path.write_bytes(b"ab\r\n")
    assert _raises(ValueError, lambda: scan_file(path, encoding=name)) == (
        f"unknown text encoding: {name!r}"
    )
    assert _raises(ValueError, lambda: normalize_file(path, encoding=name)).startswith("unknown")
    assert path.read_bytes() == b"ab\r\n"


@pytest.mark.parametrize("name", ["", "no-such-codec", "utf\x008", "\ud800", "undefined"])
def test_unusable_codec_names_are_value_errors(tmp_path: Path, name: str) -> None:
    path = tmp_path / "a.txt"
    path.write_bytes(b"a")
    assert _raises(ValueError, lambda: scan_file(path, encoding=name)).startswith("unknown")


def test_type_names_are_cut_and_never_run_code() -> None:
    long_type = type("T" * 500, (), {})
    message = _raises(TypeError, lambda: normalize(long_type()))
    assert message == "expected str or bytes, got " + "T" * 40 + "..."

    class Meta(type):
        @property
        def __name__(cls) -> str:  # type: ignore[override]
            raise RuntimeError("must not run")

    class Shy(metaclass=Meta):
        pass

    assert _raises(TypeError, lambda: counts(Shy())) == "expected str or bytes, got Shy"  # type: ignore[arg-type]


def test_a_path_with_a_nul_byte_is_a_value_error(tmp_path: Path) -> None:
    with pytest.raises(ValueError):
        scan_file(os.path.join(tmp_path, "a\x00b"))


def test_decoding_errors_keep_their_type_and_a_short_message(tmp_path: Path) -> None:
    path = tmp_path / "a.txt"
    path.write_bytes(b"ok\r\n" + b"\xff" * 100_000)
    with pytest.raises(UnicodeDecodeError) as raised:
        normalize_file(path, breaks="unicode")
    assert len(str(raised.value)) <= BOUND
    assert path.read_bytes().startswith(b"ok\r\n")


def test_bytes_with_a_unicode_set_name_the_set_only() -> None:
    for call in (
        lambda: counts(b"a", breaks="unicode"),
        lambda: normalize(b"a", breaks="splitlines"),
        lambda: Normalizer(breaks="unicode").feed(b"a"),
    ):
        assert _raises(ValueError, call).endswith("needs decoded text, not bytes")


def test_mixing_chunk_types_names_the_stream_type() -> None:
    stream: Any = Normalizer()
    stream.feed(b"a")
    assert _raises(TypeError, lambda: stream.feed("b")) == "this stream carries bytes, not a mix"
