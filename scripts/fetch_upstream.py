"""Fetch the third-party sources listed in tests/upstream/MANIFEST.json.

They are the ground truth some tests read (the Unicode line break data and UAX #14, the
CPython documentation of str.splitlines and universal newlines, git's convert.c and the
gitattributes documentation). They are not committed and not shipped: each download is
checked against the size and SHA-256 in the manifest, and a mismatch keeps nothing.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import urllib.request
from pathlib import Path

MANIFEST = Path(__file__).resolve().parents[1] / "tests" / "upstream" / "MANIFEST.json"
FOLDER = Path(os.environ.get("EOLNORM_UPSTREAM", str(MANIFEST.parent)))


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    FOLDER.mkdir(parents=True, exist_ok=True)
    failed = False
    for name, entry in manifest.items():
        with urllib.request.urlopen(entry["url"], timeout=60) as response:
            data = response.read()
        if len(data) != entry["size"] or hashlib.sha256(data).hexdigest() != entry["sha256"]:
            print(f"{name}: size or sha256 does not match the manifest", file=sys.stderr)
            failed = True
            continue
        (FOLDER / name).write_bytes(data)
        print(f"{name}: ok")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
