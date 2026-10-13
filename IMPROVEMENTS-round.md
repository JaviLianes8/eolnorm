# eolnorm improvement round

Progress:
- [x] Brainstorm ranked improvements (this file)
- [x] Boundary sets: ASCII (default), UAX #14 mandatory breaks, `str.splitlines`
- [x] `bytes` input, `keep_lone_cr` (git `text` semantics), honest type errors
- [x] Streaming `Normalizer` (CRLF split across chunks, running counts)
- [x] `is_binary` (git text=auto heuristic), BOM sniffing, UTF-16 and UTF-32
- [x] File helpers: `scan_file`, `normalize_file` with an atomic in-place rewrite
- [x] Command line tool (`eolnorm`, `python -m eolnorm`)
- [x] Contracts: live git ground truth, UCD data, interpreter scan, typing, README, wheel e2e
- [x] Mutation run (guards removed one at a time, each must fail the suite)
- [x] Docs: README, CHANGELOG, docstrings, packaging metadata
- [x] Gates: ruff format, ruff check, mypy --strict, pytest
- [x] Independent review findings fixed with regression tests
- [ ] Pull request opened, guard clean

## Starting point

`0.1.0` (not on PyPI) ships `detect`, `normalize` and `counts` over `str`, recognising only
CR, LF and CRLF. Read as a user who has files from many editors and platforms:

- Only three boundaries. Text from mainframes (NEL, U+0085), word processors (U+2028,
  U+2029) or form-feed paginated sources is reported as having no line breaks, while
  `str.splitlines` in the same program splits it. There is no way to ask for either set.
- `str` only. Files are bytes; decoding a latin-1 file as UTF-8 to fix its endings fails,
  and decoding then encoding is not byte-exact. The ASCII endings are the same bytes in
  every ASCII-compatible encoding, so bytes can be handled without decoding at all.
- Git's checkin rule (`text eol=lf`) only strips a CR that precedes an LF and leaves a lone
  CR alone; `normalize` always rewrites a lone CR, so it cannot reproduce what git stores.
- No streaming: a CRLF split across two chunks would become two endings if a caller
  normalized chunk by chunk.
- No file support: no binary detection, no BOM handling, no UTF-16, no safe rewrite. A naive
  `open(...).write(...)` loses the file on a crash halfway and follows no symlink rules.
- Bad arguments: a `bytes` value fails deep inside `re`, a wrong `to` gives a generic error.
- Packaging: no keywords, no Python classifiers, README examples never run, no wheel test.

## Sources (fetched 2026-10-13)

- UAX #14 revision 57 (Unicode 18.0.0), https://www.unicode.org/reports/tr14/: classes BK
  (mandatory break), CR, LF and NL; rules LB4 (always break after BK), LB5 (break after CR,
  LF and NL, but never between CR and LF) and LB6.
- LineBreak.txt 18.0.0, https://www.unicode.org/Public/UCD/latest/ucd/LineBreak.txt: BK is
  U+000B..U+000C, U+2028 and U+2029; CR is U+000D; LF is U+000A; NL is U+0085. Not committed
  (third-party data): `scripts/fetch_vectors.py` fetches it into a gitignored folder checked
  against a tracked MANIFEST; the test that reads it skips when it is absent.
- Python `str.splitlines`, https://docs.python.org/3/library/stdtypes.html#str.splitlines: the
  UAX #14 set plus U+001C, U+001D and U+001E. The test also scans every code point with the
  running interpreter, so the set is checked against the implementation, not only the page.
- gitattributes, https://git-scm.com/docs/gitattributes: `text` normalizes to LF in the index
  on every checkin; `text=auto` lets git decide whether a file is text; `eol=crlf` converts
  to CRLF on checkout.
- git `convert.c` at commit `6de20f6092dcf9bdb1c8efe03db4b70c82b423dd`,
  https://github.com/git/git/blob/6de20f6092dcf9bdb1c8efe03db4b70c82b423dd/convert.c:
  `gather_stats` and `convert_is_binary` (a NUL, a lone CR, or fewer than 128 printable bytes
  per non-printable one makes a file binary; BS, HT, ESC and FF count as printable, DEL as not,
  and a final Ctrl-Z is not counted), `crlf_to_git` (explicit `text` removes a CR only when an
  LF follows) and `crlf_to_worktree` (an LF not preceded by CR becomes CRLF).
- The installed git (2.54) is used as live ground truth by the tests: the same samples go
  through `git add` and `git checkout` and must match `normalize` byte for byte.

## Ranked improvements

1. **Boundary sets.** `breaks="ascii"` (default, CR, LF, CRLF), `"unicode"` (the UAX #14
   mandatory breaks: adds VT, FF, NEL, LS, PS) and `"splitlines"` (adds FS, GS, RS too).
   `counts` keys follow the chosen set; `detect` names a single kind or says "mixed".
2. **Bytes without decoding.** `counts`, `detect` and `normalize` take `bytes` for the ASCII
   set and return the same type, so any ASCII-compatible encoding is handled byte-exactly.
   The Unicode sets need decoded text and refuse bytes with a clear error.
3. **Git semantics.** `keep_lone_cr=True` reproduces `text eol=lf` checkin and `eol=crlf`
   checkout exactly, checked against the real git binary.
4. **Streaming.** `Normalizer.feed(chunk, final=False)` holds back a trailing CR until the
   next chunk shows whether an LF follows; running `counts` and `detected`.
5. **Binary and encodings.** `is_binary` applies git's text=auto statistics (the lone CR
   rule is left out, since converting old Mac files is a use case here). Files with a UTF-8,
   UTF-16 or UTF-32 BOM are decoded with the matching codec and written back with the same
   BOM; an explicit `encoding` covers BOM-less UTF-16 and other non-ASCII-compatible codecs.
6. **Safe file rewrite.** `normalize_file` writes a temporary file in the same folder,
   flushes and fsyncs it, copies the mode and replaces the original atomically (through
   symlinks to their target). Unchanged files are not touched; `dry_run` only reports.
   `scan_file` reports without writing.
7. **Command line tool.** `eolnorm FILE...` reports, `--to lf` fixes, `--check` exits 1 when a
   file would change (pre-commit style), `-` filters stdin to stdout. Exit 2 on bad input.
8. **Contracts that bite.** Live git ground truth, UCD data (fetched, not committed), an
   interpreter scan for `splitlines`, chunk-split properties, a mypy snippet, executed README
   examples, an installed-wheel e2e, and a mutation run.
9. **Docs and packaging.** README with runnable examples and exact rules, CHANGELOG 0.2.0,
   classifiers and keywords.

Left out on purpose: final-newline and trailing-whitespace fixes (other tools own those), a
recursive directory walker with ignore rules (shell globs and `git ls-files` do this better),
emulating `core.autocrlf` index lookups (git's "already committed with CRLF" rule needs the
index), and EBCDIC codecs (an explicit `encoding` already covers them).

## Verification

- Gates: `ruff format --check .`, `ruff check .`, `mypy --strict src` (also `src tests`) and
  `pytest` exit 0 on Windows with Python 3.13 (158 passed, 2 skipped: the POSIX mode test and
  the wheel e2e). On the second machine with Python 3.14 and `EOLNORM_E2E=1` the full suite
  passes (159 passed, 1 skipped): it builds the wheel, installs it in a fresh venv, drives the
  API from an empty folder, and runs the installed `eolnorm` script and `python -m eolnorm`.
- Live git 2.54: 310 samples through `text eol=lf` checkin, 310 through `eol=crlf` checkout and
  over 440 through `text=auto` (including the 1 in 128 boundary and the final Ctrl-Z rule)
  match `normalize` and `is_binary` byte for byte.
- Boundary sets: every code point checked against the running interpreter's
  `str.splitlines`, and against classes BK, CR, LF and NL in the fetched LineBreak.txt.
- Mutations: 74 guards removed or altered one at a time across every module (boundary sets,
  CRLF pairing, argument checks, lone CR handling, chunk holding and counting, every binary
  statistic, byte order marks and codec rules, the binary check with explicit encodings,
  the atomic writer's realpath, fsync, copymode, cleanup, folder and read-only rules, and the
  command's exit codes, flags and stdin rules). All are killed except one equivalent mutant
  (adding DEL to a list that only filters bytes below 0x20). The bytecode cache was disabled
  and purged before each run, and the baseline was green before and after.
- Independent review: 13 findings, all fixed with regression tests (stdin now follows the file
  rules for marks, codecs and binary data; an explicit ASCII-compatible encoding still skips
  binary files; a named codec only honours its own marks; read-only files are refused on
  every system; folder sync errors after the rename are ignored; a rejected stream chunk
  leaves the stream usable; reports are hashable; unencodable paths no longer turn a fix into
  exit 2; `--keep-lone-cr` needs `--to`; README wording and atomic-write tests tightened).
