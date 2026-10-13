"""Build the wheel, install it in a throwaway venv and drive the installed package.

Slow and needs the build backend, so it runs only with EOLNORM_E2E=1.
"""

from __future__ import annotations

import os
import subprocess
import sys
import venv
import zipfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

pytestmark = pytest.mark.skipif(
    os.environ.get("EOLNORM_E2E") != "1", reason="set EOLNORM_E2E=1 to build"
)

PROGRAM = r"""
import codecs, importlib.metadata, importlib.resources, pathlib, sys
import eolnorm as e

assert "site-packages" in e.__file__, e.__file__
assert importlib.metadata.version("eolnorm") == e.__version__
assert importlib.resources.files("eolnorm").joinpath("py.typed").is_file()
assert len(e.__all__) == 12

assert e.normalize("a\r\nb\rc") == "a\nb\nc"
assert e.normalize(b"x\ry\r\n", "crlf", keep_lone_cr=True) == b"x\ry\r\n"
assert e.detect("a\x85b", breaks="unicode") == "nel"
assert e.counts("a\x1eb", breaks="splitlines")["rs"] == 1
n = e.Normalizer("lf")
assert n.feed(b"a\r") + n.feed(b"\n", final=True) == b"a\n" and n.detected == "crlf"
assert e.is_binary(b"\x00") and not e.is_binary(b"text\r\n")
path = pathlib.Path(sys.argv[1])
path.write_bytes(codecs.BOM_UTF16_BE + "one\r\ntwo\r\n".encode("utf-16-be"))
report = e.normalize_file(path)
assert (report.encoding, report.bom, report.changed) == ("utf-16-be", True, True)
assert path.read_bytes() == codecs.BOM_UTF16_BE + "one\ntwo\n".encode("utf-16-be")
try:
    e.normalize(b"a", breaks="unicode")
except ValueError:
    pass
else:
    raise AssertionError("bytes accepted with the unicode set")
print("e2e ok")
"""


def _run(*cmd: str | Path, cwd: Path | None = None, stdin: bytes | None = None) -> bytes:
    result = subprocess.run(
        [str(c) for c in cmd], cwd=cwd, input=stdin, capture_output=True, check=False
    )
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    return result.stdout


def test_installed_wheel_end_to_end(tmp_path: Path) -> None:
    dist = tmp_path / "dist"
    _run(sys.executable, "-m", "build", "--wheel", "--outdir", dist, ROOT)
    (wheel,) = dist.glob("eolnorm-*.whl")
    names = zipfile.ZipFile(wheel).namelist()
    assert not [name for name in names if "vectors" in name or name.startswith("tests/")]

    env_dir = tmp_path / "venv"
    venv.create(env_dir, with_pip=True)
    bindir = env_dir / ("Scripts" if sys.platform == "win32" else "bin")
    python = bindir / "python"
    _run(python, "-m", "pip", "install", "-q", wheel)

    # Run from an empty folder so the source tree cannot shadow the install.
    work = tmp_path / "work"
    work.mkdir()
    out = _run(python, "-I", "-c", PROGRAM, work / "utf16.txt", cwd=work)
    assert out.decode().splitlines() == ["e2e ok"]

    (work / "a.txt").write_bytes(b"x\r\ny\r\n")
    script = bindir / ("eolnorm.exe" if sys.platform == "win32" else "eolnorm")
    assert _run(script, "a.txt", cwd=work).decode().splitlines() == ["a.txt: crlf (crlf=2)"]
    check = subprocess.run([str(script), "--to", "lf", "--check", "a.txt"], cwd=work, check=False)
    assert check.returncode == 1
    assert _run(script, "--to", "lf", "a.txt", cwd=work).decode().strip() == "fixed a.txt"
    assert (work / "a.txt").read_bytes() == b"x\ny\n"
    filtered = _run(python, "-I", "-m", "eolnorm", "--to", "crlf", "-", cwd=work, stdin=b"a\nb")
    assert filtered == b"a\r\nb"
