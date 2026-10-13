"""Normalize a stream chunk by chunk, keeping CRLF whole across chunk borders."""

from __future__ import annotations

from typing import AnyStr, cast

from ._eol import counts, detected_from, normalize
from ._kinds import Breaks, Detected, Style, check_breaks, check_style, kinds


class Normalizer:
    """Incremental `normalize` with running `counts`, for text or bytes chunks.

    A chunk that ends in CR is held back by one character until the next chunk shows
    whether an LF follows. Pass ``final=True`` with the last chunk (it may be empty) to
    release it. All chunks of one stream must be the same type, ``str`` or ``bytes``.
    """

    def __init__(
        self, to: Style = "lf", *, breaks: Breaks = "ascii", keep_lone_cr: bool = False
    ) -> None:
        if not isinstance(keep_lone_cr, bool):
            raise TypeError("keep_lone_cr must be a bool")
        self._to = check_style(to)
        self._breaks = check_breaks(breaks)
        self._keep = keep_lone_cr
        self._tally: dict[str, int] = dict.fromkeys(kinds(self._breaks), 0)
        self._pending: str | bytes = ""
        self._kind: type | None = None

    def feed(self, chunk: AnyStr, final: bool = False) -> AnyStr:
        """Return the normalized output that is safe to emit after this chunk."""
        if not isinstance(chunk, (str, bytes)):
            raise TypeError(f"expected str or bytes, got {type(chunk).__name__}")
        if self._kind is None:
            self._kind = str if isinstance(chunk, str) else bytes
            self._pending = chunk[:0]
        elif not isinstance(chunk, self._kind):
            raise TypeError(f"this stream carries {self._kind.__name__}, not a mix")
        buffer = cast(AnyStr, self._pending) + chunk
        hold = buffer.endswith("\r") if isinstance(buffer, str) else buffer.endswith(b"\r")
        if hold and not final:
            buffer, self._pending = buffer[:-1], buffer[-1:]
        else:
            self._pending = buffer[:0]
        for name, count in counts(buffer, breaks=self._breaks).items():
            self._tally[name] += count
        return normalize(buffer, self._to, breaks=self._breaks, keep_lone_cr=self._keep)

    @property
    def counts(self) -> dict[str, int]:
        """Endings seen so far in the input; a held-back CR is not counted yet."""
        return dict(self._tally)

    @property
    def detected(self) -> Detected:
        """`detect` over the input seen so far."""
        return detected_from(self._tally)
