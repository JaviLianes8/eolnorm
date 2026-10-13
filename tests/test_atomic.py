"""The in-place rewrite is atomic, keeps the mode, follows symlinks and skips no-ops."""

from __future__ import annotations

import os
import stat
import sys
from pathlib import Path

import pytest

from eolnorm import normalize_file


def _file(tmp_path: Path, data: bytes) -> Path:
    path = tmp_path / "f.txt"
    path.write_bytes(data)
    return path


def test_an_unchanged_file_is_not_rewritten(tmp_path: Path) -> None:
    path = _file(tmp_path, b"a\nb\n")
    os.utime(path, ns=(1_000_000_000, 1_000_000_000))
    assert not normalize_file(path).changed
    assert path.stat().st_mtime_ns == 1_000_000_000


def test_a_failed_replace_keeps_the_original_and_leaves_no_temporary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _file(tmp_path, b"a\r\n")

    def broken(source: str, target: str) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(os, "replace", broken)
    with pytest.raises(OSError, match="disk full"):
        normalize_file(path)
    assert path.read_bytes() == b"a\r\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["f.txt"]


def test_the_new_bytes_are_flushed_before_the_rename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _file(tmp_path, b"a\r\n")
    seen: list[bytes] = []
    real_replace = os.replace

    def spy(source: str, target: str) -> None:
        seen.append(Path(source).read_bytes())
        assert Path(source).parent == path.parent
        real_replace(source, target)

    monkeypatch.setattr(os, "replace", spy)
    normalize_file(path)
    assert seen == [b"a\n"]
    assert path.read_bytes() == b"a\n"


def test_fsync_is_called_on_the_new_file(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[int] = []
    real_fsync = os.fsync

    def spy(fd: int) -> None:
        calls.append(fd)
        real_fsync(fd)

    monkeypatch.setattr(os, "fsync", spy)
    normalize_file(_file(tmp_path, b"a\r\n"))
    assert calls


@pytest.mark.skipif(sys.platform == "win32", reason="POSIX permission bits")
def test_the_mode_is_kept(tmp_path: Path) -> None:
    path = _file(tmp_path, b"#!/bin/sh\r\necho hi\r\n")
    path.chmod(0o751)
    normalize_file(path)
    assert stat.S_IMODE(path.stat().st_mode) == 0o751


def test_the_mode_is_copied_to_the_replacement(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = _file(tmp_path, b"a\r\n")
    copied: list[tuple[str, str]] = []
    monkeypatch.setattr("shutil.copymode", lambda src, dst: copied.append((src, dst)))
    normalize_file(path)
    assert len(copied) == 1
    assert Path(copied[0][0]) == path.resolve()


def test_a_symlink_is_followed_and_kept(tmp_path: Path) -> None:
    target = _file(tmp_path, b"a\r\n")
    link = tmp_path / "link.txt"
    try:
        link.symlink_to(target)
    except OSError:
        pytest.skip("symlinks need extra rights on this system")
    normalize_file(link)
    assert link.is_symlink()
    assert target.read_bytes() == b"a\n"
