"""The README examples run and print what they say; metadata agrees with the code."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import eolnorm

ROOT = Path(__file__).resolve().parents[1]


def _readme() -> str:
    return (ROOT / "README.md").read_text(encoding="utf-8")


def _blocks() -> list[str]:
    return re.findall(r"```python\n(.*?)```", _readme(), flags=re.DOTALL)


def test_the_readme_has_its_five_examples() -> None:
    assert len(_blocks()) == 5


@pytest.mark.parametrize("index", range(5))
def test_each_example_prints_what_its_comments_say(
    index: int, capsys: pytest.CaptureFixture[str]
) -> None:
    block = _blocks()[index]
    exec(compile(block, "README.md", "exec"), {"__name__": "readme"})
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


def test_every_public_name_appears_in_the_readme() -> None:
    for name in eolnorm.__all__:
        assert f"`{name}" in _readme(), name


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
