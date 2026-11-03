"""The 1.0.0 surface: names, signatures, defaults, types, examples and identity are pinned."""

from __future__ import annotations

import dataclasses
import doctest
import inspect
import typing
from typing import get_args

import pytest

import eolnorm
from eolnorm import FileReport, Normalizer

P = inspect.Parameter
POS, KW, EMPTY = P.POSITIONAL_OR_KEYWORD, P.KEYWORD_ONLY, P.empty

SIGNATURES: dict[str, list[tuple[str, typing.Any, object]]] = {
    "counts": [("text", POS, EMPTY), ("breaks", KW, "ascii")],
    "detect": [("text", POS, EMPTY), ("breaks", KW, "ascii")],
    "normalize": [
        *[("text", POS, EMPTY), ("to", POS, "lf")],
        *[("breaks", KW, "ascii"), ("keep_lone_cr", KW, False)],
    ],
    "is_binary": [("data", POS, EMPTY)],
    "scan_file": [("path", POS, EMPTY), ("breaks", KW, "ascii"), ("encoding", KW, None)],
    "normalize_file": [
        *[("path", POS, EMPTY), ("to", POS, "lf"), ("breaks", KW, "ascii")],
        *[("keep_lone_cr", KW, False), ("encoding", KW, None), ("dry_run", KW, False)],
    ],
}
METHODS = {
    "__init__": [
        *[("self", POS, EMPTY), ("to", POS, "lf")],
        *[("breaks", KW, "ascii"), ("keep_lone_cr", KW, False)],
    ],
    "feed": [("self", POS, EMPTY), ("chunk", POS, EMPTY), ("final", POS, False)],
}


def _shape(function: typing.Any) -> list[tuple[str, typing.Any, object]]:
    return [(p.name, p.kind, p.default) for p in inspect.signature(function).parameters.values()]


@pytest.mark.parametrize("name", sorted(SIGNATURES))
def test_function_signatures_are_pinned(name: str) -> None:
    assert _shape(getattr(eolnorm, name)) == SIGNATURES[name]


@pytest.mark.parametrize("name", sorted(METHODS))
def test_normalizer_signatures_are_pinned(name: str) -> None:
    assert _shape(getattr(Normalizer, name)) == METHODS[name]


def test_normalizer_exposes_exactly_feed_counts_and_detected() -> None:
    public = {name for name in vars(Normalizer) if not name.startswith("_")}
    assert public == {"feed", "counts", "detected"}
    assert isinstance(vars(Normalizer)["counts"], property)
    assert isinstance(vars(Normalizer)["detected"], property)


def test_file_report_is_a_frozen_dataclass_with_pinned_fields() -> None:
    fields = [(f.name, f.default) for f in dataclasses.fields(FileReport)]
    missing = dataclasses.MISSING
    assert fields == [
        *[("path", missing), ("binary", missing), ("encoding", missing), ("bom", missing)],
        *[("counts", missing), ("detected", missing), ("changed", False)],
    ]
    report = FileReport("a", False, None, False, {"lf": 0, "crlf": 0, "cr": 0}, "none")
    with pytest.raises(dataclasses.FrozenInstanceError):
        report.changed = True  # type: ignore[misc]
    assert hash(report) == hash(dataclasses.replace(report, counts={"lf": 9}))


def test_the_type_aliases_name_their_values() -> None:
    assert get_args(eolnorm.Style) == ("lf", "crlf", "cr")
    assert get_args(eolnorm.Breaks) == ("ascii", "unicode", "splitlines")
    kinds = ("lf", "crlf", "cr", "vt", "ff", "fs", "gs", "rs", "nel", "ls", "ps")
    assert get_args(eolnorm.Kind) == kinds
    flat = [value for part in get_args(eolnorm.Detected) for value in get_args(part)]
    assert flat == [*kinds, "mixed", "none"]


def test_every_annotation_resolves_at_run_time() -> None:
    for name in SIGNATURES:
        assert typing.get_type_hints(getattr(eolnorm, name))
    for member in (Normalizer.__init__, Normalizer.feed, FileReport):
        assert typing.get_type_hints(member)
    for prop in ("counts", "detected"):
        assert typing.get_type_hints(getattr(Normalizer, prop).fget)


def test_the_module_exposes_nothing_public_beyond_all() -> None:
    public = sorted(name for name in vars(eolnorm) if not name.startswith("_"))
    assert public == sorted(eolnorm.__all__)


def test_public_classes_report_the_package_as_their_module() -> None:
    for cls in (FileReport, Normalizer):
        assert cls.__module__ == "eolnorm"
        assert cls.__qualname__ == cls.__name__
    assert Normalizer.feed.__module__ == "eolnorm"


def _examples() -> dict[str, int]:
    finder = doctest.DocTestFinder()
    found: dict[str, int] = {}
    modules = [eolnorm, *(m for n, m in vars(eolnorm).items() if inspect.ismodule(m))]
    for module in modules:
        for test in finder.find(module):
            name = test.name.replace(module.__name__, "eolnorm", 1)
            found[name] = max(found.get(name, 0), len(test.examples))
    return found


def test_every_public_name_has_a_runnable_example() -> None:
    found = _examples()
    wanted = [f"eolnorm.{name}" for name in SIGNATURES]
    wanted += ["eolnorm", "eolnorm.FileReport", "eolnorm.Normalizer"]
    wanted += [f"eolnorm.Normalizer.{name}" for name in ("feed", "counts", "detected")]
    for name in wanted:
        assert found.get(name, 0) > 0, name


def test_the_package_docstring_documents_every_alias() -> None:
    for alias in ("Style", "Breaks", "Kind", "Detected"):
        assert f"``{alias}``" in (eolnorm.__doc__ or ""), alias
