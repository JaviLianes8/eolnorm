"""Normalize a stream chunk by chunk, keeping CRLF whole across chunk borders."""

from __future__ import annotations

from typing import AnyStr, cast

from ._checks import flag, text_or_bytes
from ._eol import convert, detected_from
from ._kinds import Breaks, Detected, Style, check_breaks, check_style, kinds, sequence, tally


class Normalizer:
    r"""Incremental `normalize` with running `counts`, for ``str`` or ``bytes`` chunks.

    It takes the same options as `normalize`. A chunk that ends in CR is held back by one
    character until the next chunk shows whether an LF follows, so a CRLF split across two
    chunks is still one ending. Pass ``final=True`` with the last chunk (it may be empty)
    to release it. The first chunk decides whether the stream carries ``str`` or
    ``bytes``; every later chunk must be the same type. Bad arguments are refused before
    anything changes, so a rejected chunk leaves the stream as it was.

    >>> stream = Normalizer("lf")
    >>> stream.feed(b"one\r") + stream.feed(b"\ntwo\r") + stream.feed(b"", final=True)
    b'one\ntwo\n'
    >>> stream
    Normalizer('lf', breaks='ascii', keep_lone_cr=False)
    """

    def __init__(
        self, to: Style = "lf", *, breaks: Breaks = "ascii", keep_lone_cr: bool = False
    ) -> None:
        self._to = check_style(to)
        self._breaks = check_breaks(breaks)
        self._keep = flag("keep_lone_cr", keep_lone_cr)
        self._tally: dict[str, int] = dict.fromkeys(kinds(self._breaks), 0)
        self._pending: str | bytes = ""
        self._kind: type[str] | type[bytes] | None = None

    def __repr__(self) -> str:
        options = f"breaks={self._breaks!r}, keep_lone_cr={self._keep!r}"
        return f"{type(self).__name__}({self._to!r}, {options})"

    def feed(self, chunk: AnyStr, final: bool = False) -> AnyStr:
        r"""Take the next chunk and return the normalized output that is safe to emit.

        >>> stream = Normalizer("crlf")
        >>> stream.feed("end\r"), stream.feed("", final=True)
        ('end', '\r\n')
        """
        exact = text_or_bytes(chunk)
        last = flag("final", final)
        kind = type(exact)
        if kind is bytes and self._breaks != "ascii":
            raise ValueError(f"breaks={self._breaks!r} needs decoded text, not bytes")
        if self._kind is not None and kind is not self._kind:
            raise TypeError(f"this stream carries {self._kind.__name__}, not a mix")
        pending = self._pending if self._kind is not None else exact[:0]
        buffer = cast(AnyStr, pending) + cast(AnyStr, exact)
        cr = "\r" if isinstance(buffer, str) else b"\r"
        if buffer.endswith(cr) and not last:
            buffer, pending = buffer[:-1], buffer[-1:]
        else:
            pending = buffer[:0]
        counted = tally(buffer, self._breaks)
        output = convert(buffer, sequence(self._to), self._breaks, self._keep)
        # New objects rather than in-place updates, so a copy of the stream stays separate.
        self._tally = {name: count + counted[name] for name, count in self._tally.items()}
        self._pending, self._kind = pending, kind
        return cast(AnyStr, output)

    @property
    def counts(self) -> dict[str, int]:
        r"""Endings seen so far, as `counts` reports them; a held-back CR is not counted yet.

        >>> stream = Normalizer()
        >>> _ = stream.feed("a\r\nb\r")
        >>> stream.counts
        {'lf': 0, 'crlf': 1, 'cr': 0}
        """
        return dict(self._tally)

    @property
    def detected(self) -> Detected:
        r"""`detect` over the input seen so far.

        >>> stream = Normalizer()
        >>> _ = stream.feed("a\nb\r\n")
        >>> stream.detected
        'mixed'
        """
        return detected_from(self._tally)
