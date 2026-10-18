"""File rules settled for 1.0.0: marks, codecs that do not round trip, regular files only."""

from __future__ import annotations

import codecs
import errno
import os
import shutil
import stat
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from eolnorm import normalize_file, scan_file

BOM8, BOM16 = codecs.BOM_UTF8, codecs.BOM_UTF16_LE


def _file(tmp_path: Path, data: bytes) -> Path:
    path = tmp_path / "f.txt"
    path.write_bytes(data)
    return path


@pytest.mark.parametrize(
    ("data", "binary"),
    [
        (BOM8 + b"a\x00\r\n", True),
        (BOM8 + b"a" * 124 + b"\x01\r\n", True),  # 3 mark bytes + 124 = 127 printable
        (BOM8 + b"a" * 125 + b"\x01\r\n", False),  # 128 printable: text
    ],
)
def test_a_utf8_mark_does_not_skip_the_binary_check(
    tmp_path: Path, data: bytes, binary: bool
) -> None:
    path = _file(tmp_path, data)
    report = normalize_file(path, breaks="unicode")
    assert report.binary is binary
    assert (report.bom, report.encoding) == ((False, None) if binary else (True, "utf-8"))
    assert path.read_bytes() == (data if binary else data.replace(b"\r\n", b"\n"))


def test_a_binary_file_has_no_mark_no_codec_and_zero_counts(tmp_path: Path) -> None:
    report = scan_file(_file(tmp_path, BOM16 + b"\x00\x00"), breaks="unicode", encoding="latin-1")
    assert (report.binary, report.bom, report.encoding, report.detected) == (
        *(True, False, None),
        "none",
    )
    assert report.counts == dict.fromkeys(["lf", "crlf", "cr", "vt", "ff", "nel", "ls", "ps"], 0)


def test_an_explicit_encoding_always_decodes_after_a_utf8_mark(tmp_path: Path) -> None:
    path = _file(tmp_path, BOM8 + b"caf\xe9\r\n")
    assert normalize_file(path, dry_run=True).changed
    with pytest.raises(UnicodeDecodeError):
        normalize_file(path, encoding="utf-8")
    assert path.read_bytes() == BOM8 + b"caf\xe9\r\n"


@pytest.mark.parametrize(
    ("data", "options", "start"),
    [
        (BOM8 + b"ab\r\n\xc3", {"encoding": "utf-8"}, 7),
        (BOM8 + b"ab\r\n\xc3", {"breaks": "unicode"}, 7),
        (BOM16 + b"a\x00\r\x00\n\x00b", {}, 8),
    ],
)
def test_decoding_error_positions_count_from_the_start_of_the_file(
    tmp_path: Path, data: bytes, options: dict[str, str], start: int
) -> None:
    path = _file(tmp_path, data)
    for function in (scan_file, normalize_file):
        with pytest.raises(UnicodeDecodeError) as raised:
            function(path, **options)  # type: ignore[arg-type]
        error = raised.value
        assert (error.start, error.end, error.object) == (start, start + 1, data)
        assert f"position {start}" in str(error)
    assert path.read_bytes() == data


@pytest.mark.parametrize(
    ("data", "encoding"),
    [
        (b"+AGEAYgBj-\r\n", "utf-7"),
        (b"\\x41\r\n", "unicode_escape"),
        (b"\x87\x90\r\n", "cp932"),  # a duplicate mapping: encodes back as 81 E0
    ],
)
def test_normalize_file_refuses_a_codec_that_does_not_give_back_the_bytes(
    tmp_path: Path, data: bytes, encoding: str
) -> None:
    path = _file(tmp_path, data)
    for dry_run in (True, False):
        with pytest.raises(ValueError, match="does not give back these bytes unchanged"):
            normalize_file(path, encoding=encoding, dry_run=dry_run)
    assert path.read_bytes() == data
    report = scan_file(path, encoding=encoding)
    assert (report.counts["crlf"], report.binary) == (1, False)


def test_a_codec_that_round_trips_is_rewritten_exactly(tmp_path: Path) -> None:
    path = _file(tmp_path, b"\x82\xa0\x81\xe0\r\n")
    assert normalize_file(path, encoding="cp932").changed
    assert path.read_bytes() == b"\x82\xa0\x81\xe0\n"


def test_a_directory_is_an_is_a_directory_error(tmp_path: Path) -> None:
    calls: list[Callable[[], object]] = [
        lambda: scan_file(tmp_path),
        lambda: normalize_file(tmp_path, dry_run=True),
    ]
    for call in calls:
        with pytest.raises(IsADirectoryError) as raised:
            call()
        assert (raised.value.errno, raised.value.filename) == (errno.EISDIR, str(tmp_path))


def _fake_stat(monkeypatch: pytest.MonkeyPatch, name: str, target: Path) -> None:
    real: Any = getattr(os, name)
    fifo = os.stat_result((stat.S_IFIFO | 0o644, 0, 0, 1, 0, 0, 0, 0, 0, 0))

    def fake(where: Any, *args: Any, **kwargs: Any) -> Any:
        if name == "fstat" or os.fspath(where) == str(target):
            return fifo
        return real(where, *args, **kwargs)

    monkeypatch.setattr(os, name, fake)


@pytest.mark.parametrize("checked", ["stat", "fstat"])
def test_a_special_file_is_refused_before_it_is_read(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, checked: str
) -> None:
    path = _file(tmp_path, b"a\r\n")
    _fake_stat(monkeypatch, checked, path)
    calls: list[Callable[[], object]] = [lambda: scan_file(path), lambda: normalize_file(path)]
    for call in calls:
        with pytest.raises(shutil.SpecialFileError) as raised:
            call()
        assert isinstance(raised.value, OSError)
        assert (raised.value.errno, raised.value.filename) == (errno.ENOTSUP, str(path))
    monkeypatch.undo()
    assert path.read_bytes() == b"a\r\n"


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="named pipes need POSIX")
def test_a_named_pipe_is_refused_without_waiting_for_a_writer(tmp_path: Path) -> None:
    fifo = tmp_path / "pipe"
    os.mkfifo(fifo)  # type: ignore[attr-defined,unused-ignore]
    with pytest.raises(shutil.SpecialFileError):
        normalize_file(fifo)
    assert stat.S_ISFIFO(os.stat(fifo).st_mode)
