"""Detect, normalize and count line endings in text, bytes, streams and files.

Four ``Literal`` type aliases name the strings the functions take and report:

- ``Style``: a target ending for `normalize`, `Normalizer` and `normalize_file`.
- ``Breaks``: a boundary set, the ``breaks=`` argument of every function but `is_binary`.
- ``Kind``: the name of one ending, a key of `counts`.
- ``Detected``: what `detect` reports, a ``Kind``, ``"mixed"`` or ``"none"``.

>>> from typing import get_args
>>> get_args(Style), get_args(Breaks)
(('lf', 'crlf', 'cr'), ('ascii', 'unicode', 'splitlines'))
>>> get_args(Kind)
('lf', 'crlf', 'cr', 'vt', 'ff', 'fs', 'gs', 'rs', 'nel', 'ls', 'ps')
>>> kind, other = get_args(Detected)
>>> kind == Kind, get_args(other)
(True, ('mixed', 'none'))
"""

from ._binary import is_binary
from ._eol import counts, detect, normalize
from ._files import FileReport, normalize_file, scan_file
from ._kinds import Breaks, Detected, Kind, Style
from ._stream import Normalizer

__version__ = "1.0.0"

# The public classes show and pickle as eolnorm.<Name>, so a pickle never depends on the
# private module that defines them; their methods follow, so doctest finds their examples.
for _cls in (FileReport, Normalizer):
    _cls.__module__ = __name__
    for _member in vars(_cls).values():
        if callable(_member) and str(getattr(_member, "__module__", "")).startswith("eolnorm._"):
            _member.__module__ = __name__
del _cls, _member

__all__ = [
    "Breaks",
    "Detected",
    "FileReport",
    "Kind",
    "Normalizer",
    "Style",
    "counts",
    "detect",
    "is_binary",
    "normalize",
    "normalize_file",
    "scan_file",
]
