"""Live ground truth: the installed git converts the same samples, byte for byte."""

from __future__ import annotations

import os
import random
import shutil
import subprocess
from pathlib import Path

import pytest

from eolnorm import is_binary, normalize

GIT = shutil.which("git")
pytestmark = pytest.mark.skipif(GIT is None, reason="git is not installed")

EDGES = [b"", b"\r", b"\n", b"\r\n", b"\r\r\n", b"\n\r", b"a\r", b"\r\n\r", b"\r\r", b"a\n\rb"]
PIECES = [b"a", b"\xc3\xa9", b" ", b"\t", b"\r\n", b"\n", b"\r", b"\x0c", b"\r\r\n"]


def _samples(pieces: list[bytes], count: int, seed: int) -> list[bytes]:
    rng = random.Random(seed)
    return [b"".join(rng.choice(pieces) for _ in range(rng.randrange(1, 16))) for _ in range(count)]


def _git(repo: Path, *args: str, stdin: bytes | None = None) -> bytes:
    assert GIT is not None
    env = {**os.environ, "GIT_CONFIG_GLOBAL": os.devnull, "GIT_CONFIG_NOSYSTEM": "1"}
    result = subprocess.run(
        [GIT, "-C", str(repo), *args], input=stdin, capture_output=True, check=True, env=env
    )
    return result.stdout


def _repo(tmp_path: Path, samples: list[bytes], attributes: str) -> Path:
    repo = tmp_path / "repo"
    _git(tmp_path, "init", "-q", str(repo))
    _git(repo, "config", "core.autocrlf", "false")
    _git(repo, "config", "core.safecrlf", "false")
    (repo / ".git" / "info" / "attributes").write_text(attributes, encoding="ascii")
    for index, sample in enumerate(samples):
        (repo / f"{index}.txt").write_bytes(sample)
    _git(repo, "add", "--", *(f"{index}.txt" for index in range(len(samples))))
    return repo


def _index_blobs(repo: Path, count: int) -> list[bytes]:
    names = "".join(f":{index}.txt\n" for index in range(count)).encode()
    out = _git(repo, "cat-file", "--batch", stdin=names)
    blobs = []
    for _ in range(count):
        header, _, out = out.partition(b"\n")
        size = int(header.split()[2])
        blobs.append(out[:size])
        out = out[size + 1 :]
    return blobs


def test_text_eol_lf_checkin_is_keep_lone_cr(tmp_path: Path) -> None:
    samples = EDGES + _samples(PIECES, 300, seed=1)
    repo = _repo(tmp_path, samples, "*.txt text eol=lf\n")
    for sample, blob in zip(samples, _index_blobs(repo, len(samples)), strict=True):
        assert blob == normalize(sample, "lf", keep_lone_cr=True), sample


def test_text_eol_crlf_checkout_is_keep_lone_cr(tmp_path: Path) -> None:
    samples = EDGES + _samples(PIECES, 300, seed=2)
    repo = _repo(tmp_path, samples, "*.txt -text\n")
    (repo / ".git" / "info" / "attributes").write_text("*.txt text eol=crlf\n", encoding="ascii")
    for index in range(len(samples)):
        (repo / f"{index}.txt").unlink()
    _git(repo, "checkout-index", "--all", "--force")
    for index, sample in enumerate(samples):
        written = (repo / f"{index}.txt").read_bytes()
        assert written == normalize(sample, "crlf", keep_lone_cr=True), sample


def _auto_samples() -> list[bytes]:
    # No lone CR here: git's text=auto calls those binary and is_binary does not.
    crafted = [b"a" * size + b"\x01\r\n" for size in range(120, 140)]
    crafted += [b"a" * size + b"\x01\x7f\n" for size in range(250, 262)]
    crafted += [b"a" * 10 + b"\r\n\x1a", b"a\r\n\x1a\x1a", b"\x1a\r\nab", b"\x1a"]
    crafted += [b"\x1b[0m\r\n" * 3, b"\b\t\x0c\r\n", b"a\x00\r\n", b"\x80\xff\r\n" * 4]
    crafted += [b"a" * 127 + b"\x1f\r\n", b"a" * 128 + b"\x1f\r\n", b"\r\n\x0b\x0e"]
    pieces = [b"a", b"\r\n", b"\n", b"\x00", b"\x01", b"\x7f", b"\x1a", b"\t", b"\x1b", b"\x80"]
    pieces += [b"a" * 64, b"a" * 128]
    return crafted + _samples(pieces, 400, seed=3)


def test_text_auto_converts_exactly_what_is_binary_calls_text(tmp_path: Path) -> None:
    samples = _auto_samples()
    repo = _repo(tmp_path, samples, "*.txt text=auto\n")
    decisions = set()
    for sample, blob in zip(samples, _index_blobs(repo, len(samples)), strict=True):
        expected = sample if is_binary(sample) else normalize(sample, "lf")
        assert blob == expected, sample
        if b"\r\n" in sample:
            decisions.add(is_binary(sample))
    assert decisions == {True, False}


def test_text_auto_leaves_a_lone_cr_file_alone_unlike_is_binary(tmp_path: Path) -> None:
    samples = [b"a\rb\r\nc\n", b"old mac\rfile\r"]
    repo = _repo(tmp_path, samples, "*.txt text=auto\n")
    assert _index_blobs(repo, len(samples)) == samples
    assert not any(is_binary(sample) for sample in samples)
