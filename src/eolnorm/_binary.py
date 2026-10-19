"""Tell text from binary the way git does, and recognise byte order marks."""

from __future__ import annotations

import codecs

from ._checks import plain, type_name

# Git counts DEL and the control bytes as non-printable, except BS, HT, ESC and FF (and
# CR and LF, which are neutral). Bytes from 0x80 up count as printable.
_NONPRINTABLE = bytes(b for b in range(0x20) if b not in b"\b\t\n\r\x1b\x0c") + b"\x7f"

# Longest first: the UTF-32 LE mark starts with the UTF-16 LE one.
BOMS: tuple[tuple[bytes, str], ...] = (
    (codecs.BOM_UTF32_LE, "utf-32-le"),
    (codecs.BOM_UTF32_BE, "utf-32-be"),
    (codecs.BOM_UTF8, "utf-8"),
    (codecs.BOM_UTF16_LE, "utf-16-le"),
    (codecs.BOM_UTF16_BE, "utf-16-be"),
)


def looks_binary(data: bytes) -> bool:
    """``is_binary`` for exact, checked bytes."""
    if b"\x00" in data:
        return True
    nonprintable = len(data) - len(data.translate(None, _NONPRINTABLE))
    printable = len(data) - nonprintable - data.count(b"\n") - data.count(b"\r")
    if data.endswith(b"\x1a"):
        nonprintable -= 1
    return (printable >> 7) < nonprintable


def is_binary(data: bytes) -> bool:
    r"""Apply git's text=auto statistics: True when the bytes look binary.

    A NUL byte, or fewer than 128 printable bytes for each non-printable one, means
    binary. CR and LF are neutral, BS, HT, ESC and FF are printable, DEL and the other
    control bytes are not, bytes from 0x80 up are printable, and a Ctrl-Z as the very last
    byte is not held against the data. Unlike git, a lone CR does not make the data binary.

    >>> is_binary(b"\x89PNG\r\n\x1a\n\x00\x00"), is_binary("caf\xe9\r\n".encode())
    (True, False)
    >>> is_binary(b"a" * 127 + b"\x01"), is_binary(b"a" * 128 + b"\x01")
    (True, False)
    >>> is_binary(b"old\rmac\rfile\r")
    False
    """
    exact = plain(data)
    if not isinstance(exact, bytes):
        raise TypeError(f"expected bytes, got {type_name(data)}")
    return looks_binary(exact)


def sniff_bom(data: bytes) -> tuple[bytes, str] | None:
    """Return the byte order mark at the start of ``data`` and its codec, if any."""
    for bom, codec in BOMS:
        if data.startswith(bom):
            return bom, codec
    return None
