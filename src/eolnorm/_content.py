"""Turn raw bytes into something to normalize (and back), honouring marks and codecs."""

from __future__ import annotations

import codecs
from dataclasses import dataclass

from ._binary import BOMS, is_binary, sniff_bom
from ._eol import normalize
from ._kinds import Breaks, Style

# Codec names (as codecs.lookup spells them) that agree with each byte order mark.
_AGREES = {
    "utf-8": {"utf-8", "utf-8-sig"},
    "utf-16-le": {"utf-16", "utf-16-le"},
    "utf-16-be": {"utf-16", "utf-16-be"},
    "utf-32-le": {"utf-32", "utf-32-le"},
    "utf-32-be": {"utf-32", "utf-32-be"},
}
_SAMPLE = "\r\n a"


@dataclass(frozen=True)
class Content:
    raw: bytes
    prefix: bytes
    body: str | bytes | None  # None: binary, left alone
    codec: str | None


def _codec(encoding: object) -> str:
    if not isinstance(encoding, str):
        raise TypeError(f"encoding must be a str or None, got {type(encoding).__name__}")
    try:
        return codecs.lookup(encoding).name
    except LookupError:
        raise ValueError(f"unknown encoding: {encoding!r}") from None


def _mark(raw: bytes, wanted: str | None) -> tuple[bytes, str] | None:
    if wanted is None:
        return sniff_bom(raw)
    # A named codec only looks for its own marks: "utf-16" data starting with U+0000 is not
    # UTF-32, and a cp1252 file may start with the bytes of a mark.
    for bom, codec in BOMS:
        if wanted in _AGREES[codec] and raw.startswith(bom):
            return bom, codec
    return None


def _ascii_compatible(codec: str) -> bool:
    try:
        return _SAMPLE.encode(codec) == _SAMPLE.encode("ascii")
    except (UnicodeError, LookupError, TypeError):
        return False


def decode(raw: bytes, breaks: Breaks, encoding: str | None) -> Content:
    """Split ``raw`` into a kept prefix (a byte order mark) and a body to normalize."""
    wanted = None if encoding is None else _codec(encoding)
    found = _mark(raw, wanted)
    if found is not None:
        bom, codec = found
        if codec == "utf-8" and breaks == "ascii":
            return Content(raw, bom, raw[len(bom) :], codec)
        return Content(raw, bom, raw[len(bom) :].decode(codec), codec)
    if wanted in ("utf-16", "utf-32"):
        raise ValueError(f"no byte order mark: name the byte order, {wanted}-le or {wanted}-be")
    if wanted is not None:
        # Without a mark utf-8-sig decodes like utf-8, but encoding with it would add one.
        codec = "utf-8" if wanted == "utf-8-sig" else wanted
        if _ascii_compatible(codec) and is_binary(raw):
            return Content(raw, b"", None, None)
        return Content(raw, b"", raw.decode(codec), codec)
    if is_binary(raw):
        return Content(raw, b"", None, None)
    if breaks == "ascii":
        return Content(raw, b"", raw, None)
    return Content(raw, b"", raw.decode("utf-8"), "utf-8")


def fix(content: Content, to: Style, breaks: Breaks, keep_lone_cr: bool) -> bytes:
    """The normalized bytes, with the same prefix and codec; binary comes back unchanged."""
    body = content.body
    if body is None:
        return content.raw
    if isinstance(body, bytes):
        return content.prefix + normalize(body, to, keep_lone_cr=keep_lone_cr)
    fixed = normalize(body, to, breaks=breaks, keep_lone_cr=keep_lone_cr)
    return content.prefix + fixed.encode(str(content.codec))
