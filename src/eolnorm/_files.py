"""Inspect and normalize files: binary detection, byte order marks, atomic rewrite."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Union

from ._atomic import write_atomic
from ._content import Content, decode, fix
from ._eol import counts, detected_from
from ._kinds import Breaks, Detected, Style, check_breaks, check_style, kinds

StrPath = Union[str, "os.PathLike[str]"]


@dataclass(frozen=True)
class FileReport:
    """What a file holds and whether normalizing it changed it (or would, in a dry run).

    ``encoding`` names the codec in play: the one a byte order mark or the caller chose, or
    utf-8 for the Unicode sets. It is None when no codec was involved, which is exact for
    any ASCII-compatible encoding. For a binary file nothing is counted or changed.
    """

    path: str
    binary: bool
    encoding: str | None
    bom: bool
    counts: dict[str, int] = field(hash=False)
    detected: Detected
    changed: bool = False


def _load(path: StrPath, breaks: Breaks, encoding: str | None) -> Content:
    return decode(Path(path).read_bytes(), breaks, encoding)


def _report(path: StrPath, content: Content, breaks: Breaks, changed: bool) -> FileReport:
    tally: dict[str, int] = dict.fromkeys(kinds(breaks), 0)
    if content.body is not None:
        tally = counts(content.body, breaks=breaks)
    return FileReport(
        path=os.fspath(path),
        binary=content.body is None,
        encoding=content.codec,
        bom=bool(content.prefix),
        counts=tally,
        detected=detected_from(tally),
        changed=changed,
    )


def scan_file(
    path: StrPath, *, breaks: Breaks = "ascii", encoding: str | None = None
) -> FileReport:
    """Read a file and report its line endings without writing anything."""
    breaks = check_breaks(breaks)
    return _report(path, _load(path, breaks, encoding), breaks, changed=False)


def normalize_file(
    path: StrPath,
    to: Style = "lf",
    *,
    breaks: Breaks = "ascii",
    keep_lone_cr: bool = False,
    encoding: str | None = None,
    dry_run: bool = False,
) -> FileReport:
    """Normalize a file in place, atomically, keeping its byte order mark and encoding.

    A binary file is left alone. A file whose bytes would not change is not rewritten.
    With ``dry_run`` the report says whether it would change and nothing is written. The
    counts describe the file as it was before.
    """
    breaks = check_breaks(breaks)
    to = check_style(to)
    if not isinstance(keep_lone_cr, bool):
        raise TypeError("keep_lone_cr must be a bool")
    content = _load(path, breaks, encoding)
    output = fix(content, to, breaks, keep_lone_cr)
    changed = output != content.raw
    if changed and not dry_run:
        write_atomic(os.fspath(path), output)
    return _report(path, content, breaks, changed=changed)
