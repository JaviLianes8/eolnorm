"""The command line with closed, failing or vanishing streams, and its bounded messages."""

from __future__ import annotations

import errno
import importlib
import io
import os
import subprocess
import sys
from pathlib import Path

import pytest

from eolnorm._cli import main


class Failing(io.TextIOWrapper):
    """A text stream whose writes fail with one errno once ``after`` writes went through."""

    def __init__(self, number: int, after: int = 0) -> None:
        super().__init__(io.BytesIO(), encoding="utf-8")
        self.number, self.after = number, after

    def write(self, text: str) -> int:
        if self.after <= 0:
            raise OSError(self.number, "simulated")
        self.after -= 1
        return super().write(text)


def _files(tmp_path: Path, count: int, data: bytes = b"a\r\n") -> list[str]:
    paths = [tmp_path / f"f{index}.txt" for index in range(count)]
    for path in paths:
        path.write_bytes(data)
    return [str(path) for path in paths]


@pytest.mark.parametrize("number", [errno.EPIPE, errno.EINVAL])
def test_a_reader_that_leaves_silences_output_but_not_the_work(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, number: int, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = _files(tmp_path, 5)
    monkeypatch.setattr(sys, "stdout", Failing(number, after=1))
    assert main(["--to", "lf", *paths]) == 0
    assert all(Path(path).read_bytes() == b"a\n" for path in paths)
    assert capsys.readouterr().err == ""
    _files(tmp_path, 5)
    monkeypatch.setattr(sys, "stdout", Failing(number))
    assert main(["--to", "lf", "--check", *paths]) == 1


def test_any_other_output_failure_is_reported_once_and_exits_two(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    paths = _files(tmp_path, 3)
    monkeypatch.setattr(sys, "stdout", Failing(errno.EIO))
    assert main(["--to", "lf", *paths]) == 2
    assert capsys.readouterr().err == "eolnorm: cannot write standard output: simulated\n"
    assert all(Path(path).read_bytes() == b"a\n" for path in paths)


def test_a_closed_standard_output_is_a_failure_when_there_is_output(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (path,) = _files(tmp_path, 1)
    monkeypatch.setattr(sys, "stdout", None)
    assert main([path]) == 2
    assert capsys.readouterr().err == "eolnorm: cannot write standard output: it is closed\n"
    assert main(["--to", "lf", path]) == 2
    assert Path(path).read_bytes() == b"a\n"
    assert main(["--to", "lf", path]) == 0  # nothing left to say
    assert main(["--to", "lf", "-"]) == 2
    assert capsys.readouterr().err.endswith("eolnorm: -: standard output is closed\n")


def test_a_closed_standard_input_is_reported(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setattr(sys, "stdin", None)
    assert main(["--to", "lf", "-"]) == 2
    assert capsys.readouterr().err == "eolnorm: -: standard input is closed\n"


def test_a_failing_read_of_standard_input_is_reported(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class Broken(io.RawIOBase):
        def readable(self) -> bool:
            return True

        def readinto(self, buffer: object) -> int:
            raise OSError(errno.EIO, "input lost")

    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BufferedReader(Broken())))
    assert main(["--to", "lf", "-"]) == 2
    assert capsys.readouterr().err == "eolnorm: -: input lost\n"


def test_an_error_line_names_the_path_once(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = str(tmp_path / "missing.txt")
    assert main([missing]) == 2
    err = capsys.readouterr().err
    assert err.startswith(f"eolnorm: {missing}: ") and err.count("missing.txt") == 1


@pytest.mark.parametrize("option", ["--to", "--breaks", "--encoding"])
def test_usage_errors_are_cut_short(option: str, capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as raised:
        main([option, "z" * 100_000, "x"])
    assert raised.value.code == 2
    message = capsys.readouterr().err.splitlines()[-1]
    assert message.startswith("eolnorm: error: ") and message.endswith("...")
    assert len(message) <= len("eolnorm: error: ") + 303


def test_importing_the_main_module_does_not_run_the_tool() -> None:
    module = importlib.import_module("eolnorm.__main__")
    assert module.main is main


def test_a_reader_closing_a_real_pipe_early(tmp_path: Path) -> None:
    # About 18 KB of output: the reader closes after the first 8 KB block, while the tool
    # (one fsync per file) still has hundreds of files to fix and report.
    names = [f"{index}.t" for index in range(1500)]
    for name in names:
        (tmp_path / name).write_bytes(b"a\r\n")
    command = [sys.executable, "-m", "eolnorm", "--to", "lf", *names]
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    child = subprocess.Popen(
        command, cwd=tmp_path, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env
    )
    assert child.stdout is not None and child.stderr is not None
    assert child.stdout.readline().startswith(b"fixed ")
    child.stdout.close()
    err = child.stderr.read()
    assert child.wait(timeout=120) == 0, err
    assert err == b""
    assert all((tmp_path / name).read_bytes() == b"a\n" for name in names)


def test_a_closed_stream_object_counts_as_a_reader_that_left(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    (path,) = _files(tmp_path, 1)
    closed = io.StringIO()
    closed.close()
    monkeypatch.setattr(sys, "stdout", closed)
    assert main(["--to", "lf", path]) == 0
    assert Path(path).read_bytes() == b"a\n"
    assert capsys.readouterr().err == ""


@pytest.mark.parametrize("stderr", [None, "closed", "failing"])
def test_losing_standard_error_never_changes_the_exit_code(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, stderr: str | None
) -> None:
    def lose() -> None:
        lost: object = None
        if stderr == "closed":
            lost = io.StringIO()
            lost.close()
        elif stderr == "failing":
            lost = Failing(errno.EIO)
        monkeypatch.setattr(sys, "stderr", lost)

    out = io.BytesIO()
    monkeypatch.setattr(sys, "stdin", io.TextIOWrapper(io.BytesIO(b"\x00\x01binary")))
    monkeypatch.setattr(sys, "stdout", io.TextIOWrapper(out, write_through=True))
    lose()
    assert main(["--to", "lf", "-"]) == 0  # the binary note is lost, the data is not
    assert out.getvalue() == b"\x00\x01binary"
    lose()
    assert main([str(tmp_path / "missing.txt"), *_files(tmp_path, 1)]) == 2


@pytest.mark.parametrize("option", ["--help", "--version"])
def test_help_and_version_into_a_reader_that_already_left(option: str) -> None:
    env = {**os.environ, "PYTHONPATH": str(Path(__file__).resolve().parents[1] / "src")}
    command = [sys.executable, "-m", "eolnorm", option]
    child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
    assert child.stdout is not None and child.stderr is not None
    child.stdout.close()
    err = child.stderr.read()
    assert child.wait(timeout=120) == 0, err
    assert err == b""
