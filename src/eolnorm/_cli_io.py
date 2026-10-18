"""Command line plumbing: output that survives a reader leaving early, bounded messages."""

from __future__ import annotations

import argparse
import contextlib
import errno
import os
import sys
from typing import NoReturn

# Messages are cut here, so a huge argument or error text is never echoed back whole.
MESSAGE_LIMIT = 300


def cut(text: str) -> str:
    return text if len(text) <= MESSAGE_LIMIT else text[:MESSAGE_LIMIT] + "..."


def reason(error: BaseException) -> str:
    """The words for ``error`` in a message: the system's own for an operating system error."""
    if isinstance(error, OSError) and error.strerror:
        return cut(str(error.strerror))
    return cut(str(error))


def _reader_left(error: BaseException) -> bool:
    # A closed pipe is EPIPE on POSIX and often EINVAL on Windows; a stream object that
    # was closed raises ValueError.
    return isinstance(error, ValueError) or getattr(error, "errno", None) in (
        errno.EPIPE,
        errno.EINVAL,
    )


def _silence(stream: object) -> None:
    # Point the descriptor at the null device: Python flushes the standard streams at
    # exit, and a failed flush there would print a warning and exit 120.
    try:
        fd = stream.fileno()  # type: ignore[attr-defined]
        null = os.open(os.devnull, os.O_WRONLY)
    except (AttributeError, OSError, ValueError):
        return
    if null != fd:  # a closed descriptor is reused by open(): then it is the null device
        os.dup2(null, fd)
        os.close(null)


class Output:
    """Standard output and error for one run of the tool.

    A reader that goes away (``eolnorm ... | head``) only silences the stream: the work
    goes on and the exit status is the one the work earned. Any other failure to write
    standard output is reported on standard error and makes the run exit 2.
    """

    def __init__(self) -> None:
        self.failed = False
        self._silenced: set[str] = set()
        for stream in (sys.stdout, sys.stderr):
            # A path the console cannot encode must not turn a finished fix into a failure.
            with contextlib.suppress(AttributeError, OSError, ValueError):
                stream.reconfigure(errors="backslashreplace")  # type: ignore[union-attr]

    def line(self, text: str) -> None:
        self._write("stdout", text + "\n")

    def note(self, text: str) -> None:
        self._write("stderr", text + "\n")

    def data(self, data: bytes) -> None:
        """Write raw bytes to standard output, after any text written before."""
        stream = sys.stdout
        if "stdout" in self._silenced:
            return
        try:
            stream.flush()
            stream.buffer.write(data)
            stream.buffer.flush()
        except (AttributeError, OSError, ValueError) as error:
            self._lost("stdout", stream, error)

    def finish(self, code: int) -> int:
        """Flush both streams; return 2 if standard output failed, else ``code``."""
        for name in ("stdout", "stderr"):
            self._write(name, "")
        return 2 if self.failed else code

    def _write(self, name: str, text: str) -> None:
        stream = getattr(sys, name)
        if stream is None or name in self._silenced:
            return
        try:
            if text:
                stream.write(text)
            stream.flush()
        except (AttributeError, OSError, ValueError) as error:
            self._lost(name, stream, error)

    def _lost(self, name: str, stream: object, error: BaseException) -> None:
        self._silenced.add(name)
        _silence(stream)
        if name == "stdout" and not _reader_left(error):
            self.failed = True
            self.note(f"eolnorm: cannot write standard output: {reason(error)}")


class Parser(argparse.ArgumentParser):
    """An argument parser whose error messages are bounded."""

    def error(self, message: str) -> NoReturn:
        super().error(cut(message))
