"""Inspect and normalize files: binary detection, byte order marks, atomic rewrite."""

from __future__ import annotations

import codecs
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Union

from ._atomic import write_atomic
from ._binary import is_binary, sniff_bom
from ._eol import counts, detected_from, normalize
from ._kinds import Breaks, Detected, Style, check_breaks, check_style, kinds

StrPath = Union[str, "os.PathLike[str]"]

# Codec names (as codecs.lookup spells them) that agree with each byte order mark.
_AGREES = {
    "utf-8": {"utf-8", "utf-8-sig"},
    "utf-16-le": {"utf-16", "utf-16-le"},
    "utf-16-be": {"utf-16", "utf-16-be"},
    "utf-32-le": {"utf-32", "utf-32-le"},
    "utf-32-be": {"utf-32", "utf-32-be"},
}


@dataclass(frozen=True)
class FileReport:
    """What a file holds and whether normalizing it changed it (or would, in a dry run).

    ``encoding`` is None when the bytes were handled without decoding, which is exact for
    any ASCII-compatible encoding. For a binary file nothing is counted or changed.
    """

    path: str
    binary: bool
    encoding: str | None
    bom: bool
    counts: dict[str, int]
    detected: Detected
    changed: bool = False


@dataclass(frozen=True)
class _Content:
    raw: bytes
    prefix: bytes
    body: str | bytes | None
    codec: str | None


def _codec(encoding: object) -> str:
    if not isinstance(encoding, str):
        raise TypeError(f"encoding must be a str or None, got {type(encoding).__name__}")
    try:
        return codecs.lookup(encoding).name
    except LookupError:
        raise ValueError(f"unknown encoding: {encoding!r}") from None


def _load(path: StrPath, breaks: Breaks, encoding: str | None) -> _Content:
    raw = Path(path).read_bytes()
    found = sniff_bom(raw)
    wanted = None if encoding is None else _codec(encoding)
    if found is not None:
        bom, codec = found
        if wanted is not None and wanted not in _AGREES[codec]:
            raise ValueError(f"file starts with a {codec} byte order mark, not {wanted}")
        if codec == "utf-8" and breaks == "ascii":
            return _Content(raw, bom, raw[len(bom) :], codec)
        return _Content(raw, bom, raw[len(bom) :].decode(codec), codec)
    if wanted in ("utf-16", "utf-32"):
        raise ValueError(f"no byte order mark: name the byte order, {wanted}-le or {wanted}-be")
    if wanted is not None:
        # Without a mark utf-8-sig decodes like utf-8, but encoding with it would add one.
        codec = "utf-8" if wanted == "utf-8-sig" else wanted
        return _Content(raw, b"", raw.decode(codec), codec)
    if is_binary(raw):
        return _Content(raw, b"", None, None)
    if breaks == "ascii":
        return _Content(raw, b"", raw, None)
    return _Content(raw, b"", raw.decode("utf-8"), "utf-8")


def _report(path: StrPath, content: _Content, breaks: Breaks, changed: bool) -> FileReport:
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
    if content.body is None:
        return _report(path, content, breaks, changed=False)
    body = content.body
    if isinstance(body, bytes):
        output = content.prefix + normalize(body, to, keep_lone_cr=keep_lone_cr)
    else:
        fixed = normalize(body, to, breaks=breaks, keep_lone_cr=keep_lone_cr)
        output = content.prefix + fixed.encode(str(content.codec))
    changed = output != content.raw
    if changed and not dry_run:
        write_atomic(os.fspath(path), output)
    return _report(path, content, breaks, changed=changed)
