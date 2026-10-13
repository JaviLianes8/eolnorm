"""The command line tool: report, check, fix, filter, and its exit codes."""

from __future__ import annotations

import codecs
import io
import sys
from pathlib import Path

import pytest

import eolnorm
from eolnorm._cli import main


def _file(tmp_path: Path, name: str, data: bytes) -> str:
    path = tmp_path / name
    path.write_bytes(data)
    return str(path)


def test_report_names_the_style_and_counts(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    crlf = _file(tmp_path, "a.txt", b"x\r\ny\r\n")
    mixed = _file(tmp_path, "b.txt", b"x\ny\r\n")
    empty = _file(tmp_path, "c.txt", b"x")
    binary = _file(tmp_path, "d.bin", b"\x00\r\n")
    assert main([crlf, mixed, empty, binary]) == 0
    assert capsys.readouterr().out.splitlines() == [
        f"{crlf}: crlf (crlf=2)",
        f"{mixed}: mixed (lf=1, crlf=1)",
        f"{empty}: none",
        f"{binary}: binary",
    ]


def test_fix_rewrites_and_names_each_changed_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dirty = _file(tmp_path, "a.txt", b"x\r\n")
    clean = _file(tmp_path, "b.txt", b"x\n")
    binary = _file(tmp_path, "c.bin", b"\x00\r\n")
    assert main(["--to", "lf", dirty, clean, binary]) == 0
    assert capsys.readouterr().out.splitlines() == [f"fixed {dirty}", f"skipped {binary}: binary"]
    assert Path(dirty).read_bytes() == b"x\n"
    assert Path(binary).read_bytes() == b"\x00\r\n"


def test_check_exits_one_and_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dirty = _file(tmp_path, "a.txt", b"x\r\n")
    assert main(["--to", "lf", "--check", dirty]) == 1
    assert capsys.readouterr().out == f"would fix {dirty}\n"
    assert Path(dirty).read_bytes() == b"x\r\n"


def test_check_exits_zero_when_all_is_clean(tmp_path: Path) -> None:
    assert main(["--to", "crlf", "--check", _file(tmp_path, "a.txt", b"x\r\n")]) == 0


def test_options_reach_the_library(tmp_path: Path) -> None:
    path = _file(tmp_path, "a.txt", "a\rb\x85c\r\n".encode("utf-16-le"))
    args = ["--to", "lf", "--keep-lone-cr", "--breaks", "unicode", "--encoding", "utf-16-le"]
    assert main([*args, path]) == 0
    assert Path(path).read_bytes() == "a\rb\nc\n".encode("utf-16-le")


def test_a_bad_file_exits_two_but_the_rest_still_run(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    good = _file(tmp_path, "a.txt", b"x\r\n")
    missing = str(tmp_path / "missing.txt")
    assert main(["--to", "lf", missing, good]) == 2
    captured = capsys.readouterr()
    assert captured.err.startswith(f"eolnorm: {missing}: ")
    assert Path(good).read_bytes() == b"x\n"


def test_decode_and_encoding_errors_exit_two(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _file(tmp_path, "a.txt", b"\x80\r\n")
    assert main(["--to", "lf", "--encoding", "utf-8", path]) == 2
    assert main(["--encoding", "nope", path]) == 2
    assert capsys.readouterr().err.count("eolnorm: ") == 2


def _pipe(monkeypatch: pytest.MonkeyPatch, data: bytes) -> io.BytesIO:
    out = io.BytesIO()
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(data)))
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(out, write_through=True))
    return out


def test_dash_filters_stdin_to_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    out = _pipe(monkeypatch, b"caf\xe9\r\nx\r")
    assert main(["--to", "crlf", "-"]) == 0
    assert out.getvalue() == b"caf\xe9\r\nx\r\n"


def test_dash_with_an_encoding_decodes(monkeypatch: pytest.MonkeyPatch) -> None:
    out = _pipe(monkeypatch, "a\u2028b".encode("utf-16-le"))
    assert main(["--to", "lf", "--breaks", "unicode", "--encoding", "utf-16-le", "-"]) == 0
    assert out.getvalue() == "a\nb".encode("utf-16-le")


def test_dash_with_bad_input_exits_two(monkeypatch: pytest.MonkeyPatch) -> None:
    _pipe(monkeypatch, b"\xff\r\n")
    assert main(["--to", "lf", "--breaks", "unicode", "-"]) == 2


def test_dash_keeps_a_utf16_mark_and_codec(monkeypatch: pytest.MonkeyPatch) -> None:
    data = codecs.BOM_UTF16_BE + "a\r\nb\r\n".encode("utf-16-be")
    out = _pipe(monkeypatch, data)
    assert main(["--to", "lf", "-"]) == 0
    assert out.getvalue() == codecs.BOM_UTF16_BE + "a\nb\n".encode("utf-16-be")


def test_dash_never_adds_a_mark(monkeypatch: pytest.MonkeyPatch) -> None:
    out = _pipe(monkeypatch, b"a\r\n")
    assert main(["--to", "lf", "--encoding", "utf-8-sig", "-"]) == 0
    assert out.getvalue() == b"a\n"


def test_dash_refuses_generic_utf16_without_a_mark(monkeypatch: pytest.MonkeyPatch) -> None:
    out = _pipe(monkeypatch, "a\r\n".encode("utf-16-le"))
    assert main(["--to", "lf", "--encoding", "utf-16", "-"]) == 2
    assert out.getvalue() == b""


def test_dash_passes_binary_through(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    data = b"\x89PNG\r\n\x1a\n\x00\r\n"
    out = _pipe(monkeypatch, data)
    assert main(["--to", "crlf", "-"]) == 0
    assert out.getvalue() == data
    assert capsys.readouterr().err == "eolnorm: -: binary, passed through unchanged\n"


def test_a_name_the_console_cannot_encode_is_still_a_success(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _file(tmp_path, "snow" + chr(0x2603) + ".txt", b"a\r\n")
    out = io.BytesIO()
    console = io.TextIOWrapper(out, encoding="ascii", newline="\n", write_through=True)
    monkeypatch.setattr(sys, "stdout", console)
    assert main(["--to", "lf", path]) == 0
    assert Path(path).read_bytes() == b"a\n"
    assert out.getvalue().decode("ascii").endswith("snow\\u2603.txt\n")


@pytest.mark.parametrize(
    "argv",
    [
        ["--keep-lone-cr", "x"],
        ["--check", "x"],
        ["-"],
        ["--to", "lf", "--check", "-"],
        ["--to", "lf", "-", "x"],
        ["--to", "lfcr", "x"],
        [],
    ],
)
def test_usage_errors_exit_two(argv: list[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        main(argv)
    assert raised.value.code == 2


def test_version(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["--version"])
    assert raised.value.code == 0
    assert capsys.readouterr().out == f"eolnorm {eolnorm.__version__}\n"
