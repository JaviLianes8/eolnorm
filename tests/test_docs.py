"""The README and GUIDE examples run and print what they say; metadata agrees with the code."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import eolnorm

ROOT = Path(__file__).resolve().parents[1]


def _readme() -> str:
    return (ROOT / "README.md").read_text(encoding="utf-8")


def _blocks(name: str = "README.md") -> list[str]:
    text = (ROOT / name).read_text(encoding="utf-8")
    return re.findall(r"```python\n(.*?)```", text, flags=re.DOTALL)


EXAMPLES = [("README.md", 5), ("GUIDE.md", 4)]


@pytest.mark.parametrize(("name", "count"), EXAMPLES)
def test_each_document_has_its_examples(name: str, count: int) -> None:
    assert len(_blocks(name)) == count


@pytest.mark.parametrize(
    ("name", "index"), [(name, index) for name, count in EXAMPLES for index in range(count)]
)
def test_each_example_prints_what_its_comments_say(
    name: str, index: int, capsys: pytest.CaptureFixture[str]
) -> None:
    block = _blocks(name)[index]
    exec(compile(block, name, "exec"), {"__name__": "example"})
    comments = re.findall(r"^# (.+)$", block, flags=re.MULTILINE)
    printed = capsys.readouterr().out.splitlines()
    assert printed == comments
    assert len(printed) >= 2


def test_the_command_line_example_matches_the_tool(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    from eolnorm._cli import main

    monkeypatch.chdir(tmp_path)
    Path("notes.txt").write_bytes(b"one\r\ntwo\r\n")
    Path("logo.png").write_bytes(b"\x89PNG\r\n\x1a\n\x00")
    transcript = []
    for argv in (["notes.txt", "logo.png"], ["--to", "lf", "--check", "notes.txt"]):
        main(argv)
        transcript += [f"$ eolnorm {' '.join(argv)}", *capsys.readouterr().out.splitlines()]
    main(["--to", "lf", "notes.txt"])
    transcript += ["$ eolnorm --to lf notes.txt", *capsys.readouterr().out.splitlines()]
    assert "\n".join(transcript) + "\n" in _readme()


@pytest.mark.parametrize("document", ["README.md", "GUIDE.md"])
def test_every_public_name_appears_in_each_document(document: str) -> None:
    text = (ROOT / document).read_text(encoding="utf-8")
    for name in eolnorm.__all__:
        assert f"`{name}" in text, name


def test_version_matches_pyproject() -> None:
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    match = re.search(r'^version = "([^"]+)"$', text, flags=re.MULTILINE)
    assert match is not None
    assert match.group(1) == eolnorm.__version__


def test_changelog_has_an_entry_for_this_version() -> None:
    text = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert f"## [{eolnorm.__version__}]" in text


def _shipped() -> list[Path]:
    return [
        *ROOT.glob("*.md"),
        *ROOT.glob("*.toml"),
        *ROOT.glob("src/**/*.py"),
        *ROOT.glob("tests/*.py"),
        *ROOT.glob("scripts/*"),
    ]


def test_no_em_dash_in_any_shipped_text() -> None:
    for path in _shipped():
        assert chr(0x2014) not in path.read_text(encoding="utf-8"), path


def test_sources_are_ascii_so_invisible_separators_cannot_hide() -> None:
    for path in [*ROOT.glob("src/**/*.py"), *ROOT.glob("tests/*.py")]:
        assert path.read_text(encoding="utf-8").isascii(), path


def test_every_source_file_stays_under_two_hundred_lines() -> None:
    for path in [*ROOT.glob("src/**/*.py"), *ROOT.glob("tests/*.py"), *ROOT.glob("scripts/*")]:
        assert len(path.read_text(encoding="utf-8").splitlines()) <= 200, path
