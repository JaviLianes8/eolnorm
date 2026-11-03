"""Upgrade an actual downloaded 0.2.0 wheel in place and compare consumer results."""

from __future__ import annotations

import os
import subprocess
import sys
import venv
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

PROGRAM = r"""
import codecs, hashlib, json, pathlib, pickle, random, sys
import eolnorm as e

assert "site-packages" in e.__file__
assert e.__version__ == sys.argv[1]
rng = random.Random(1000)
results = []
for _ in range(500):
    text = "".join(rng.choices("ab\r\n\x85\x1e\u2028", k=rng.randrange(50)))
    for breaks in ("ascii", "unicode", "splitlines"):
        for to in ("lf", "crlf", "cr"):
            for keep in (False, True):
                options = dict(breaks=breaks, keep_lone_cr=keep)
                stream = e.Normalizer(to, **options)
                output = stream.feed(text[:5]) + stream.feed(text[5:], final=True)
                results.append([e.normalize(text, to, **options), output,
                                e.counts(text, breaks=breaks), stream.counts,
                                e.detect(text, breaks=breaks), stream.detected])
    data = text.encode("utf-8")
    results.append([e.normalize(data).hex(), e.counts(data), e.is_binary(data)])
path = pathlib.Path("sample.txt")
path.write_bytes(codecs.BOM_UTF16_LE + "one\r\ntwo\r".encode("utf-16-le"))
report = e.normalize_file(path)
results.append([report.binary, report.encoding, report.bom, report.counts,
                report.detected, report.changed, path.read_bytes().hex(),
                e.scan_file(path).detected])
if sys.argv[1] == "0.2.0":
    stream = e.Normalizer()
    stream.feed(b"one\r")
    pathlib.Path("legacy.pickle").write_bytes(pickle.dumps((report, stream), protocol=4))
else:
    report, stream = pickle.loads(pathlib.Path("legacy.pickle").read_bytes())
    assert type(report) is e.FileReport and type(stream) is e.Normalizer
    assert report.encoding == "utf-16-le" and report.detected == "mixed"
    assert stream.feed(b"\ntwo", final=True) == b"\ntwo"
    assert stream.counts == {"lf": 0, "crlf": 1, "cr": 0}
print(hashlib.sha256(json.dumps(results, sort_keys=True).encode()).hexdigest())
"""


def _run(*args: str | Path, cwd: Path) -> bytes:
    result = subprocess.run(
        [str(arg) for arg in args], cwd=cwd, capture_output=True, timeout=180, check=False
    )
    assert result.returncode == 0, result.stderr.decode(errors="replace")
    return result.stdout


def test_pypi_release_upgrades_in_place(tmp_path: Path) -> None:
    previous = os.environ.get("EOLNORM_PREVIOUS_WHEEL")
    if os.environ.get("EOLNORM_E2E") != "1" or not previous:
        pytest.skip("set EOLNORM_E2E=1 and EOLNORM_PREVIOUS_WHEEL to the PyPI 0.2.0 wheel")
    old_wheel = Path(previous).resolve()
    assert old_wheel.name == "eolnorm-0.2.0-py3-none-any.whl" and old_wheel.is_file()
    dist = tmp_path / "dist"
    _run(sys.executable, "-m", "build", "--wheel", "--outdir", dist, ROOT, cwd=tmp_path)
    (wheel,) = dist.glob("eolnorm-1.0.0-*.whl")
    env = tmp_path / "env"
    venv.create(env, with_pip=True)
    scripts = env / ("Scripts" if os.name == "nt" else "bin")
    python = scripts / "python"
    command = scripts / ("eolnorm.exe" if os.name == "nt" else "eolnorm")
    _run(python, "-m", "pip", "install", "--no-index", old_wheel, cwd=tmp_path)
    before = _run(python, "-I", "-c", PROGRAM, "0.2.0", cwd=tmp_path)
    old_report = _run(command, "sample.txt", cwd=tmp_path)
    _run(python, "-m", "pip", "install", "--no-index", "--upgrade", wheel, cwd=tmp_path)
    after = _run(python, "-I", "-c", PROGRAM, "1.0.0", cwd=tmp_path)
    assert before == after
    assert _run(command, "sample.txt", cwd=tmp_path) == old_report
    assert _run(command, "--version", cwd=tmp_path).strip() == b"eolnorm 1.0.0"
    _run(python, "-m", "pip", "check", cwd=tmp_path)
