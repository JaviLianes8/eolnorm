"""Detect, normalize and count line endings in text, bytes, streams and files."""

from __future__ import annotations

from ._binary import is_binary
from ._eol import counts, detect, normalize
from ._files import FileReport, normalize_file, scan_file
from ._kinds import Breaks, Detected, Kind, Style
from ._stream import Normalizer

__version__ = "0.2.0"

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
