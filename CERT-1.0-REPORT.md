# eolnorm 1.0.0 certification report

The 1.0.0 certification bar (19 items) applied to eolnorm. Nothing is on PyPI yet
(`https://pypi.org/pypi/eolnorm/json` answered 404 on 2026-10-18), so there is no release to
upgrade from; every behaviour change is still listed against 0.2.0, the last tagged state of
`main` (ba7c9e9).

Progress:
- [x] Branch `release/1.0.0` created from `main` (ba7c9e9, 0.2.0)
- [x] Baseline gates on 0.2.0
- [ ] API review and 1.0.0 changes (item 1)
- [ ] Errors, typing, docstrings and doctests (items 2 to 5)
- [ ] Ground truth: sources fetched live, reference programs (item 7)
- [ ] Contract, fuzz and author mutation round (items 6, 9, 18)
- [ ] Docs: README, GUIDE, CHANGELOG (items 11, 12)
- [ ] Packaging, e2e, every Python (items 8, 10, 13, 14)
- [ ] Gates (item 15)
- [ ] PR and trace guard
- [ ] Five QA lenses report PASS (item 19)
- [ ] Independent reviewer reports PASS (item 16)

## Baseline on 0.2.0 (before any change)

Fresh clone of `main` at ba7c9e9 on the laptop, CPython 3.14.6, with the fetched
`LineBreak.txt` and `EOLNORM_E2E=1`: `ruff format --check .`, `ruff check .` and
`mypy --strict src tests` exit 0; `pytest` 159 passed, 1 skipped (the POSIX permission-bits
test). No public docstring had a runnable example and no doctest existed.

Defects found in 0.2.0 by reading and then reproducing:

- A non-text codec (`encoding="hex"`, `"base64"`, `"rot13"`, `"zlib"`) raised `LookupError`
  from the decoder; the command line printed a traceback and exited 1.
- A codec that does not give back the same bytes changed more than line endings:
  `normalize_file(path, encoding="utf-7")` rewrote `+AGEAYgBj-\r\n` as `abc\n`.
- A file starting with a UTF-8 byte order mark skipped the binary check: a mark followed by
  NUL and control bytes was rewritten, although the README said the check runs for every
  ASCII-compatible encoding.
- `dry_run` and `Normalizer.feed(final=...)` took any truthy value (`dry_run="no"` was a dry
  run) while `keep_lone_cr` had to be a `bool`.
- Error messages quoted the whole argument: a 100,000-character style, boundary set,
  encoding name or type name gave a message of the same size; the command line echoed huge
  `--to` and `--encoding` values.
- `copy.copy` of a `Normalizer` shared its running counts with the original.
- `FileReport` and `Normalizer` reported private modules (`eolnorm._files`,
  `eolnorm._stream`), so pickles depended on them; the package exposed a stray public
  `annotations` name.
- A directory gave `PermissionError` on Windows and `IsADirectoryError` elsewhere.
- A `UnicodeDecodeError` position counted from the end of the byte order mark, not from the
  start of the file.
- A `str` subclass with its own `__radd__` replaced the output of `Normalizer.feed`, and a
  `bytes` subclass with its own `__buffer__` made `normalize` and `counts` read other bytes
  than `is_binary`.
- The command line: a closed standard input gave a traceback; when its reader closed the
  output pipe, every later line was reported as a failure of the file being processed
  (`eolnorm: f660.txt: [Errno 22] Invalid argument`) and the process exited 120.
