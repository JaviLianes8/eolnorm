"""Turn raw bytes into something to normalize (and back), honouring marks and codecs."""

from __future__ import annotations

import codecs
from dataclasses import dataclass
from typing import cast

from ._binary import BOMS, looks_binary, sniff_bom
from ._checks import plain, shown, type_name
from ._eol import convert
from ._kinds import Breaks, Style, sequence

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


def check_encoding(encoding: object) -> str | None:
    """The codec's canonical name, or None; only text encodings are accepted."""
    if encoding is None:
        return None
    exact = plain(encoding)
    if not isinstance(exact, str):
        raise TypeError(f"encoding must be a str or None, got {type_name(encoding)}")
    try:
        name = codecs.lookup(exact).name
        # Bytes-to-bytes and text-to-text codecs (hex, zlib, rot13) refuse both calls.
        "".encode(name)
        b"".decode(name)
    except (LookupError, ValueError):
        # ValueError: a name with a NUL or a lone surrogate cannot even be looked up.
        raise ValueError(f"unknown text encoding: {shown(exact)}") from None
    return name


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


def _text(raw: bytes, start: int, codec: str) -> str:
    try:
        return raw[start:].decode(codec)
    except UnicodeDecodeError as error:
        # Positions count from the start of the file, byte order mark included.
        begin, end = error.start + start, error.end + start
        raise UnicodeDecodeError(error.encoding, raw, begin, end, error.reason) from None


def decode(raw: bytes, breaks: Breaks, wanted: str | None) -> Content:
    """Split ``raw`` into a kept prefix (a byte order mark) and a body to normalize.

    ``wanted`` is a name from `check_encoding`. The body stays undecoded bytes only when no
    codec was named, the set is the ASCII one and no byte order mark is present: a mark
    names its codec, so the body after it is always decoded (and must be valid).
    """
    found = _mark(raw, wanted)
    if found is not None:
        bom, codec = found
    elif wanted in ("utf-16", "utf-32"):
        raise ValueError(f"no byte order mark: name the byte order, {wanted}-le or {wanted}-be")
    else:
        # Without a mark utf-8-sig decodes like utf-8, but encoding with it would add one.
        bom, codec = b"", "utf-8" if wanted in (None, "utf-8-sig") else wanted
    # git's statistics hold for ASCII-compatible bytes only: UTF-16 text is full of NULs.
    if _ascii_compatible(codec) and looks_binary(raw):
        return Content(raw, b"", None, None)
    if wanted is None and breaks == "ascii" and not bom:
        return Content(raw, b"", raw, None)
    return Content(raw, bom, _text(raw, len(bom), codec), codec)


def fix(content: Content, to: Style, breaks: Breaks, keep_lone_cr: bool) -> bytes:
    """The normalized bytes, with the same prefix and codec; binary comes back unchanged.

    A codec that does not give back the original bytes from the decoded text (UTF-7, some
    CJK codecs with duplicate mappings) would change more than line endings: refused.
    """
    body, target = content.body, sequence(to)
    if body is None:
        return content.raw
    if isinstance(body, bytes):
        return content.prefix + cast(bytes, convert(body, target, "ascii", keep_lone_cr))
    codec = cast(str, content.codec)
    try:
        same = content.prefix + body.encode(codec) == content.raw
    except UnicodeEncodeError:
        same = False
    if not same:
        raise ValueError(f"the {shown(codec)} codec does not give back these bytes unchanged")
    fixed = cast(str, convert(body, target, breaks, keep_lone_cr))
    return content.prefix + fixed.encode(codec)
