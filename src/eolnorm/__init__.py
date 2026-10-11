"""Detect, normalize and count line endings in text."""

from __future__ import annotations

from ._eol import Detected, Style, counts, detect, normalize

__version__ = "0.1.0"

__all__ = ["Detected", "Style", "counts", "detect", "normalize"]
