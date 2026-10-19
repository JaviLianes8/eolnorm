"""Argument checks shared by the public functions, with messages of bounded size."""

from __future__ import annotations

from collections.abc import Collection
from typing import cast

# A message quotes at most this many characters of a caller's value or of a type name, so a
# huge argument is never echoed back whole.
LIMIT = 40

# Read through type's own descriptor: a metaclass cannot replace a class's name with a
# property that runs code or raises.
_NAME = type.__dict__["__name__"]


def shown(text: str) -> str:
    """The repr of ``text``, cut after LIMIT characters.

    >>> shown("lf")
    "'lf'"
    >>> shown("x" * 100) == repr("x" * 40) + "..."
    True
    """
    return repr(text) if len(text) <= LIMIT else repr(text[:LIMIT]) + "..."


def type_name(value: object) -> str:
    """The name of ``value``'s class, cut after LIMIT characters.

    >>> type_name(3.5), type_name(None)
    ('float', 'NoneType')
    """
    name = str.__str__(_NAME.__get__(type(value)))
    return name if len(name) <= LIMIT else name[:LIMIT] + "..."


def plain(value: object) -> str | bytes | None:
    """An exact ``str`` or ``bytes`` with the value of ``value``, or None for other types.

    The class is read with ``type()``, so an object that only claims to be a string through
    ``__class__`` is refused, and a subclass is copied through the base type's own slots,
    so none of its methods runs.

    >>> class Text(str):
    ...     def __add__(self, other):
    ...         return "replaced"
    >>> type(plain(Text("a"))), plain(Text("a")) + "b", plain(bytearray(b"a"))
    (<class 'str'>, 'ab', None)
    """
    kind = type(value)
    if issubclass(kind, str):
        text = cast(str, value)
        return text if kind is str else str.__str__(text)
    if issubclass(kind, bytes):
        data = cast(bytes, value)
        return data if kind is bytes else bytes.__getitem__(data, slice(None))
    return None


def text_or_bytes(value: object) -> str | bytes:
    """``value`` as an exact ``str`` or ``bytes``; TypeError for anything else.

    >>> text_or_bytes(memoryview(b"a"))
    Traceback (most recent call last):
    TypeError: expected str or bytes, got memoryview
    """
    exact = plain(value)
    if exact is None:
        raise TypeError(f"expected str or bytes, got {type_name(value)}")
    return exact


def flag(name: str, value: object) -> bool:
    """``value`` when it is a real ``bool``; TypeError otherwise.

    >>> flag("final", True)
    True
    >>> flag("final", 1)
    Traceback (most recent call last):
    TypeError: final must be a bool, got int
    """
    if type(value) is not bool:
        raise TypeError(f"{name} must be a bool, got {type_name(value)}")
    return value is True


def option(what: str, value: object, choices: Collection[str]) -> str:
    """``value`` as an exact ``str`` when it is one of ``choices``.

    A value of another type raises TypeError and an unknown string raises ValueError.

    >>> option("style", "crlf", ("lf", "crlf"))
    'crlf'
    >>> option("style", "LF", ("lf", "crlf"))
    Traceback (most recent call last):
    ValueError: unknown style: 'LF'
    """
    exact = plain(value)
    if not isinstance(exact, str):
        raise TypeError(f"{what} must be a str, got {type_name(value)}")
    if exact not in choices:
        raise ValueError(f"unknown {what}: {shown(exact)}")
    return exact
