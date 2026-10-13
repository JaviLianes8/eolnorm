"""The public API is typed: mypy infers results and rejects bad calls."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

api = pytest.importorskip("mypy.api")

SRC = Path(__file__).resolve().parents[1] / "src"

SNIPPET = """
import eolnorm as e
reveal_type(e.normalize("a"))
reveal_type(e.normalize(b"a", "crlf"))
reveal_type(e.counts(b"a"))
reveal_type(e.detect("a", breaks="unicode"))
reveal_type(e.Normalizer().feed(b"a"))
reveal_type(e.Normalizer().feed("a", final=True))
reveal_type(e.normalize_file("f").changed)
reveal_type(e.scan_file("f").encoding)
reveal_type(e.is_binary(b"a"))
e.normalize("a", "lfcr")
e.normalize("a", breaks="all")
e.normalize(5)
e.detect("a", "unicode")
e.is_binary("text")
e.normalize_file("f", keep_lone_cr="yes")
x: e.Kind = "nel"
y: e.Detected = "mixed"
z: e.Style = "crlf"
w: e.Breaks = "splitlines"
"""


@pytest.fixture(scope="module")
def mypy_output(tmp_path_factory: pytest.TempPathFactory) -> str:
    folder = tmp_path_factory.mktemp("typing")
    target = folder / "snippet.py"
    target.write_text(SNIPPET, encoding="utf-8")
    config = folder / "mypy.ini"
    config.write_text(f"[mypy]\nmypy_path = {SRC.as_posix()}\n", encoding="utf-8")
    cache = str(folder / "cache")
    out, err, _ = api.run(
        ["--strict", "--config-file", str(config), "--cache-dir", cache, str(target)]
    )
    return str(out) + str(err)


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        (3, r"builtins\.str"),
        (4, r"builtins\.bytes"),
        (5, r"builtins\.dict\[builtins\.str, builtins\.int\]"),
        (6, r"Literal\['lf'\] \| .*Literal\['ps'\] \| Literal\['mixed'\] \| Literal\['none'\]"),
        (7, r"builtins\.bytes"),
        (8, r"builtins\.str"),
        (9, r"builtins\.bool"),
        (10, r"builtins\.str \| None"),
        (11, r"builtins\.bool"),
    ],
)
def test_results_are_typed(mypy_output: str, line: int, expected: str) -> None:
    # Older mypy releases print the builtins prefix, newer ones do not.
    pattern = expected.replace(r"builtins\.", r"(builtins\.)?")
    assert re.search(rf'snippet\.py:{line}: note: Revealed type is "{pattern}"', mypy_output), (
        mypy_output
    )


@pytest.mark.parametrize(
    ("line", "code"),
    [(12, "arg-type"), (13, "arg-type"), (14, "type-var"), (15, "call-arg"), (16, "arg-type")],
)
def test_wrong_calls_are_rejected(mypy_output: str, line: int, code: str) -> None:
    assert re.search(rf"snippet\.py:{line}: error: .*\[{code}\]", mypy_output), mypy_output


def test_bool_argument_is_typed(mypy_output: str) -> None:
    assert re.search(r"snippet\.py:17: error: .*\[arg-type\]", mypy_output), mypy_output


def test_the_type_aliases_accept_their_values(mypy_output: str) -> None:
    assert not re.search(r"snippet\.py:(1[89]|2[01]): error", mypy_output), mypy_output
