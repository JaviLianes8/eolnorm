"""Inspect and normalize files: binary detection, byte order marks, atomic rewrite."""

from __future__ import annotations

import errno
import os
import shutil
import stat
from dataclasses import dataclass, field

from ._atomic import write_atomic
from ._checks import flag, plain, type_name
from ._content import Content, check_encoding, decode, fix
from ._eol import detected_from
from ._kinds import Breaks, Detected, Style, check_breaks, check_style, kinds, tally


@dataclass(frozen=True)
class FileReport:
    r"""What a file holds and whether normalizing it changed it (or would, in a dry run).

    ``path`` is the path as given, as a string, ``bom`` whether a byte order mark was found
    (and kept), and ``counts`` and ``detected`` describe the file before any change, as
    `counts` and `detect` do. ``encoding`` names the codec in play, as ``codecs.lookup``
    spells it: the one a byte order mark or the caller chose, or utf-8 for the Unicode sets.
    It is None when no codec was involved, which is exact for any ASCII-compatible encoding.
    A ``binary`` file is left alone and not interpreted at all: its ``encoding`` is None,
    ``bom`` is False and every count is zero.

    >>> report = FileReport("a.txt", False, None, False, {"lf": 2, "crlf": 0, "cr": 0}, "lf")
    >>> report  # doctest: +NORMALIZE_WHITESPACE
    FileReport(path='a.txt', binary=False, encoding=None, bom=False,
               counts={'lf': 2, 'crlf': 0, 'cr': 0}, detected='lf', changed=False)
    """

    path: str
    binary: bool
    encoding: str | None
    bom: bool
    counts: dict[str, int] = field(hash=False)
    detected: Detected
    changed: bool = False


def _path(path: object) -> str:
    try:
        name = plain(os.fspath(path))  # type: ignore[call-overload]
    except TypeError:
        name = None
    if not isinstance(name, str):
        raise TypeError(f"path must be a str or os.PathLike[str], got {type_name(path)}")
    return name


def _regular(mode: int, name: str) -> None:
    # Only regular files: reading a pipe could block forever, and replacing one (or a
    # device) with a regular file would change what the path is.
    if stat.S_ISDIR(mode):
        raise IsADirectoryError(errno.EISDIR, os.strerror(errno.EISDIR), name)
    if not stat.S_ISREG(mode):
        raise shutil.SpecialFileError(errno.ENOTSUP, "not a regular file", name)


# Opening a pipe without O_NONBLOCK waits for a writer; O_BINARY keeps Windows from
# translating the bytes.
_FLAGS = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)
_FLAGS |= getattr(os, "O_NOCTTY", 0)


def _read(name: str) -> bytes:
    _regular(os.stat(name).st_mode, name)
    # Checked again on the open descriptor, in case the path was replaced in between.
    with open(os.open(name, _FLAGS), "rb") as handle:
        _regular(os.fstat(handle.fileno()).st_mode, name)
        return handle.read()


def _report(name: str, content: Content, breaks: Breaks, changed: bool) -> FileReport:
    counted: dict[str, int] = dict.fromkeys(kinds(breaks), 0)
    if content.body is not None:
        counted = tally(content.body, breaks)
    return FileReport(
        path=name,
        binary=content.body is None,
        encoding=content.codec,
        bom=bool(content.prefix),
        counts=counted,
        detected=detected_from(counted),
        changed=changed,
    )


def scan_file(
    path: str | os.PathLike[str], *, breaks: Breaks = "ascii", encoding: str | None = None
) -> FileReport:
    r"""Read a file and report its line endings without writing anything.

    >>> import pathlib, tempfile
    >>> with tempfile.TemporaryDirectory() as folder:
    ...     path = pathlib.Path(folder, "notes.txt")
    ...     _ = path.write_bytes(b"one\r\ntwo\r\n")
    ...     report = scan_file(path)
    >>> report.detected, report.counts, report.changed
    ('crlf', {'lf': 0, 'crlf': 2, 'cr': 0}, False)
    """
    name = _path(path)
    chosen = check_breaks(breaks)
    wanted = check_encoding(encoding)
    return _report(name, decode(_read(name), chosen, wanted), chosen, changed=False)


def normalize_file(
    path: str | os.PathLike[str],
    to: Style = "lf",
    *,
    breaks: Breaks = "ascii",
    keep_lone_cr: bool = False,
    encoding: str | None = None,
    dry_run: bool = False,
) -> FileReport:
    r"""Normalize a file in place, atomically, keeping its byte order mark and encoding.

    A binary file is left alone. A file whose bytes would not change is not rewritten.
    With ``dry_run`` the report says whether it would change and nothing is written. The
    counts describe the file as it was before.

    >>> import codecs, pathlib, tempfile
    >>> with tempfile.TemporaryDirectory() as folder:
    ...     path = pathlib.Path(folder, "notes.txt")
    ...     _ = path.write_bytes(codecs.BOM_UTF16_LE + "a\r\nb\r\n".encode("utf-16-le"))
    ...     report = normalize_file(path, "lf")
    ...     after = path.read_bytes()
    >>> report.encoding, report.bom, report.detected, report.changed
    ('utf-16-le', True, 'crlf', True)
    >>> after == codecs.BOM_UTF16_LE + "a\nb\n".encode("utf-16-le")
    True
    """
    name = _path(path)
    chosen = check_breaks(breaks)
    target = check_style(to)
    keep = flag("keep_lone_cr", keep_lone_cr)
    wanted = check_encoding(encoding)
    rehearse = flag("dry_run", dry_run)
    content = decode(_read(name), chosen, wanted)
    output = fix(content, target, chosen, keep)
    changed = output != content.raw
    if changed and not rehearse:
        write_atomic(name, output)
    return _report(name, content, chosen, changed=changed)
