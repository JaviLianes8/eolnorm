"""Replace a file's contents atomically: readers see the old bytes or the new, never half."""

from __future__ import annotations

import contextlib
import errno
import os
import shutil
import stat
import tempfile


def write_atomic(path: str, data: bytes) -> None:
    # Rewrite the target of a symlink, not the link itself, and stay on its filesystem so
    # the final rename cannot fall back to a copy.
    real = os.path.realpath(path)
    folder = os.path.dirname(real)
    # Windows refuses to replace a read-only file while POSIX would replace it silently;
    # refuse everywhere so the outcome does not depend on the system.
    if not os.access(real, os.W_OK):
        raise PermissionError(errno.EACCES, "file is read-only", path)
    fd, temporary = tempfile.mkstemp(dir=folder, prefix=".eolnorm-", suffix=".tmp")
    try:
        with os.fdopen(fd, "wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        shutil.copymode(real, temporary)
        os.replace(temporary, real)
    except BaseException:
        _discard(temporary)
        raise
    _sync_folder(folder)


def _discard(temporary: str) -> None:
    # copymode may have made the temporary file read-only, which blocks deleting it on
    # Windows.
    with contextlib.suppress(OSError):
        os.chmod(temporary, stat.S_IWRITE | stat.S_IREAD)
    with contextlib.suppress(OSError):
        os.unlink(temporary)


def _sync_folder(folder: str) -> None:
    # On POSIX the rename is durable only once the directory entry is flushed too.
    if not hasattr(os, "O_DIRECTORY"):
        return
    try:
        descriptor = os.open(folder, os.O_RDONLY | os.O_DIRECTORY)
    except OSError:
        return
    try:
        os.fsync(descriptor)
    except OSError:
        pass
    finally:
        os.close(descriptor)
