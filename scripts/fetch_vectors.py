"""Fetch the Unicode data files listed in tests/vectors/unicode/MANIFEST.txt.

The files are third-party and are not committed. Each download is checked against the size
and SHA-256 in the manifest; a mismatch aborts without keeping the file.
"""

from __future__ import annotations

import hashlib
import sys
import urllib.request
from pathlib import Path

FOLDER = Path(__file__).resolve().parents[1] / "tests" / "vectors" / "unicode"


def main() -> int:
    lines = (FOLDER / "MANIFEST.txt").read_text(encoding="utf-8").splitlines()
    base = next(line for line in lines if line.startswith("# URL: "))[len("# URL: ") :]
    for line in lines:
        if not line or line.startswith("#"):
            continue
        digest, size, name = line.split()
        with urllib.request.urlopen(base.replace("<name>", name), timeout=60) as response:
            data = response.read()
        if len(data) != int(size) or hashlib.sha256(data).hexdigest() != digest:
            print(f"{name}: size or sha256 does not match the manifest", file=sys.stderr)
            return 1
        (FOLDER / name).write_bytes(data)
        print(f"{name}: ok")
    return 0


if __name__ == "__main__":
    sys.exit(main())
