"""Paths the command line shows: control characters escaped, error lines bounded."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import pytest

from eolnorm import FileReport, _cli
from eolnorm._cli import main

# Clears the screen, retitles the window and rings the bell when written raw.
HOSTILE = "a\x1b[2J\x1b]0;pwned\x07\n\x85\x7f\u2028b"
ESCAPED = "a\\x1b[2J\\x1b]0;pwned\\x07\\n\\x85\\x7f\\u2028b"
LIMIT = 300


def _report(path: str, binary: bool = False, changed: bool = False) -> FileReport:
    counted = {"lf": 0 if binary else 1, "crlf": 0, "cr": 0}
    return FileReport(path, binary, None, False, counted, "none" if binary else "lf", changed)


def test_report_fix_and_skip_lines_escape_control_characters(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    # Most systems refuse such names, so the library calls are replaced; POSIX runs it real.
    def fix(path: str, to: str, **options: Any) -> FileReport:
        return _report(path, binary=path.endswith("bin"), changed=not path.endswith("bin"))

    monkeypatch.setattr(_cli, "scan_file", lambda path, **options: _report(path))
    monkeypatch.setattr(_cli, "normalize_file", fix)
    assert main([HOSTILE]) == 0
    assert main(["--to", "lf", HOSTILE, HOSTILE + "bin"]) == 0
    assert main(["--to", "lf", "--check", HOSTILE]) == 1
    captured = capsys.readouterr()
    assert captured.out.splitlines() == [
        f"{ESCAPED}: lf (lf=1)",
        f"fixed {ESCAPED}",
        f"skipped {ESCAPED}bin: binary",
        f"would fix {ESCAPED}",
    ]
    assert captured.err == ""


@pytest.mark.skipif(os.name == "nt", reason="Windows file names cannot hold control characters")
def test_a_real_file_name_with_control_characters_is_escaped(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = tmp_path / HOSTILE
    path.write_bytes(b"x\r\n")
    assert main(["--to", "lf", str(path)]) == 0
    assert capsys.readouterr().out == f"fixed {tmp_path}{os.sep}{ESCAPED}\n"
    assert path.read_bytes() == b"x\n"


def test_an_error_line_escapes_control_characters(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main([str(tmp_path / ("missing" + HOSTILE))]) == 2
    err = capsys.readouterr().err
    assert err.startswith(f"eolnorm: {tmp_path}{os.sep}missing{ESCAPED}: ")
    assert err.count("\n") == 1
    assert not any(char in err for char in "\x1b\x07\x85\x7f\u2028")


def test_an_error_line_cuts_a_huge_path(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    path = str(tmp_path / ("x" * 5000))
    assert main([path, path]) == 2
    lines = capsys.readouterr().err.splitlines()
    assert len(lines) == 2
    for line in lines:
        assert line.startswith("eolnorm: " + path[:LIMIT] + "...: ")
        assert len(line) <= len("eolnorm: ") + LIMIT + 3 + 2 + LIMIT + 3


def test_a_usage_error_escapes_control_characters(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        main(["x", "--z" + HOSTILE])
    assert raised.value.code == 2
    message = capsys.readouterr().err.splitlines()[-1]
    assert message == f"eolnorm: error: unrecognized arguments: --z{ESCAPED}"
