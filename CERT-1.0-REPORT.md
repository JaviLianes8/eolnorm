# eolnorm 1.0.0 certification report

The 1.0.0 certification bar (19 items) applied to eolnorm. Nothing is on PyPI
(`https://pypi.org/pypi/eolnorm/json` answered 404 on 2026-10-18 and again on 2026-10-19), so
there is no release to upgrade from; every behaviour change is listed in the CHANGELOG
against 0.2.0, the last state of `main` (ba7c9e9).

Progress:
- [x] Branch `release/1.0.0` created from `main` (ba7c9e9, 0.2.0)
- [x] Baseline gates on 0.2.0
- [x] API review and 1.0.0 changes (item 1)
- [x] Contracts for every 1.0.0 change (signatures, errors, subclasses, pickles, file rules,
  command line streams)
- [x] Errors, typing, docstrings and doctests (items 2 to 5)
- [x] Ground truth: sources fetched live, reference programs (item 7)
- [x] Contract, fuzz and author mutation round (items 6, 9, 18)
- [x] Docs: README, GUIDE, CHANGELOG (items 11, 12)
- [x] Packaging, e2e, every Python (items 8, 10, 13, 14)
- [x] Gates (item 15)
- [x] PR and trace guard
- [ ] Five QA lenses report PASS (item 19)
- [ ] Independent reviewer reports PASS (item 16)

## Scorecard (author)

| # | Item | Result |
| --- | --- | --- |
| 1 | Public API reviewed for stability | PASS: 12 names, signatures and defaults pinned by `tests/test_contract_api.py`; every change since 0.2.0 in the CHANGELOG |
| 2 | `__all__` exact, no private imports in docs | PASS: `tests/test_contract.py`; README and GUIDE import from `eolnorm` only |
| 3 | Docstrings with runnable examples, doctests | PASS: every public function, class, method and property has an example; 18 doctest items; README (5 blocks) and GUIDE (4 blocks) run as tests |
| 4 | Typed end to end | PASS: `mypy --strict src tests`, `py.typed` shipped, consumer typing checked by `tests/test_typing.py` |
| 5 | Typed, documented, bounded errors | PASS: `TypeError`, `ValueError`, `UnicodeDecodeError` and `OSError` subclasses, table in the GUIDE; messages quote at most 40 characters of a value (command line: 300) |
| 6 | Contract tests of every public name | PASS |
| 7 | Real ground truth | PASS: 8 sources fetched live with a hash manifest (re-fetched 2026-10-19, all hashes match), the installed git, the running interpreter, `eolify` 0.1.7 |
| 8 | Real e2e from the wheel | PASS: wheel installed in a fresh venv, driven from an empty folder, CLI by subprocess; no PyPI release to upgrade from |
| 9 | Seeded fuzz, no crash, hang or blowup | PASS: `tests/test_fuzz.py` |
| 10 | Supported Pythons | PASS: CPython 3.10.19, 3.11.5, 3.12.12, 3.13.2, 3.14.2, 3.14.2t; 3.13t not installed here |
| 11 | README and `twine check` | PASS: `twine check --strict`, absolute links, badge, honest comparison |
| 12 | Dated CHANGELOG section | PASS: 1.0.0, 2026-10-19 |
| 13 | pyproject 1.0.0, Production/Stable | PASS: version 1.0.0, classifiers 3.10 to 3.14, MIT, URLs, keywords, no runtime dependencies |
| 14 | sdist and wheel contents | PASS: checked by `tests/test_e2e_wheel.py` and by hand |
| 15 | Gates each exit 0 | PASS: see Gates |
| 16 | Independent reviewer | pending (next stage) |
| 17 | PR and trace guard | PR from `release/1.0.0`, trace guard CLEAN; merge and publish left to the maintainer |
| 18 | Contracts bite (mutations) | PASS: author 53 mutants, 52 killed at once, the survivor killed by a new contract |
| 19 | Five independent QA lenses | pending (next stage) |

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

## API, errors, typing and docs (items 1 to 5, 11, 12)

The API changes are listed in the CHANGELOG under 1.0.0 and pinned by
`tests/test_contract_api.py` (names, signatures, defaults, keyword-only options, result
types, module identity of the classes, docstring examples present), `tests/test_errors.py`
(type and size of every error), `tests/test_subclasses.py`, `tests/test_pickle_copy.py`,
`tests/test_files_rules.py` and `tests/test_cli_streams.py`. `GUIDE.md` was added: every
public name in detail, the error table and the command line contract; its examples and the
README's run as tests (`tests/test_docs.py`), which also check that every public name
appears in both, the CLI transcript in the README matches the tool, the version agrees
with `pyproject.toml` and the CHANGELOG, no em dash anywhere, sources ASCII and under 200
lines.

README "Why" facts were checked on 2026-10-19: `eolify` 0.1.7 from PyPI
(`https://pypi.org/pypi/eolify/json`, "powered by Rust", `Mode` has `LF` and `CRLF` only,
public names `normalize_text`, `normalize_file`, `normalize_stream`) was installed and run
here: it converts a lone CR, leaves NEL and U+2028 alone, converts the CR LF of a PNG
header, and `normalize_file(p, p, Mode.LF, overwrite=True)` left a 3-byte file empty on
Windows.

## Ground truth (item 7)

Sources fetched by `scripts/fetch_upstream.py`, listed with URL, revision, size, sha256 and
licence in `tests/upstream/MANIFEST.json`, not committed and not shipped; their tests skip
without them. Fetched 2026-10-18 and fetched again 2026-10-19 with every hash matching.

| Source | URL | Checked by |
| --- | --- | --- |
| `LineBreak.txt` 18.0.0 | https://www.unicode.org/Public/18.0.0/ucd/LineBreak.txt | `test_boundaries.py`: the `unicode` set is exactly the code points of the classes LB4 and LB5 name |
| UAX #14 rev. 57 | https://www.unicode.org/reports/tr14/tr14-57.html | `test_boundaries.py`: the classes are read from rules LB4 and LB5 (BK, CR, LF, NL, and CR x LF) |
| `stdtypes.rst` (CPython v3.14.0) | https://raw.githubusercontent.com/python/cpython/v3.14.0/Doc/library/stdtypes.rst | `test_spec_python.py`: the `str.splitlines` table is the `splitlines` set |
| `glossary.rst` | https://raw.githubusercontent.com/python/cpython/v3.14.0/Doc/glossary.rst | `test_spec_python.py`: the universal newlines are the `ascii` set |
| `io.rst`, `functions.rst` | https://raw.githubusercontent.com/python/cpython/v3.14.0/Doc/library/io.rst and .../functions.rst | `test_spec_python.py`: the documented newline translation, then 3,000 random texts read through `io.TextIOWrapper` equal `normalize(text, "lf")` |
| `convert.c` (git v2.54.0) | https://raw.githubusercontent.com/git/git/v2.54.0/convert.c | `test_spec_git.py`: the statistics of `gather_stats` and `convert_is_binary` are parsed from the source, ported, and compared with `is_binary` on 20,000+ samples; the CR loops of `crlf_to_git` and `crlf_to_worktree` match `keep_lone_cr=True` |
| `gitattributes.adoc` | https://raw.githubusercontent.com/git/git/v2.54.0/Documentation/gitattributes.adoc | `test_spec_git.py`: the documented `text`, `eol` and `text=auto` semantics |

Reference programs run in the suite: the installed git (`test_git.py`: `git add` under
`text eol=lf`, `git checkout-index` under `eol=crlf` and `text=auto` on hundreds of samples,
byte for byte), the running interpreter (`str.splitlines` over every code point, `io`
readers and writers on random texts) and `eolify` 0.1.7 (`test_oracle_eolify.py`, 10,000
texts and 2,000 chunked streams, LF and CRLF; skipped when not installed). Hand-written
expectations are labelled as such in the tests.

## Fuzz and robustness (item 9)

`tests/test_fuzz.py`, all seeded: 4,000 random texts per property over every set and style
(endings kept in number, all converted, idempotent), `bytes` against `str` on the ASCII set,
`keep_lone_cr` against an independent rewrite (lone CRs hidden behind a mark), 2,000 random
byte streams cut at random against one call, 1,500 random files with byte order marks and
10 codecs or none (each either normalizes and scans back clean, or raises `ValueError` and leaves
the file byte for byte), 14 hostile argument values through every public name (only
`TypeError`, `ValueError` or `OSError`, messages under 200 characters, file untouched), and
six adversarial inputs timed at 20,000 and 320,000 units plus a stream of one-byte chunks
(linear: 16 times the input stays under 80 times the time; quadratic would be 256).

## Author mutation round (item 18)

53 mutants over every module, each applied alone to a private copy of a fresh clone of
184f747 on another machine, the full suite run with `-x` and a 300 s per-test limit, the
fetched sources, git and `eolify` 0.1.7 present. 52 killed at once. M34 survived: no test
asked for `"utf-32"` without a mark (only `"utf-16"`); 67fc3a7 adds the contract for both,
and M34 applied to 67fc3a7 now fails it.

| Mutant | Module | Change | Caught by |
| --- | --- | --- | --- |
| M01 | `_binary.py` | ESC counted as non-printable | `tests/test_binary.py::test_bs_ht_esc_and_ff_are_printable` |
| M02 | `_binary.py` | DEL counted as printable | `tests/test_binary.py::test_del_and_other_controls_are_not_printable` |
| M03 | `_binary.py` | ratio 64 instead of 128 | `src/eolnorm/_binary.py::eolnorm._binary.is_binary` |
| M04 | `_binary.py` | off by one at the ratio limit | `src/eolnorm/_binary.py::eolnorm._binary.is_binary` |
| M05 | `_binary.py` | Ctrl-Z forgiven at the start, not the end | `tests/test_binary.py::test_a_final_ctrl_z_is_forgiven` |
| M06 | `_binary.py` | a single NUL no longer binary | `tests/test_binary.py::test_a_nul_byte_anywhere_is_binary` |
| M07 | `_binary.py` | wrong endianness for the UTF-32 LE mark | `tests/test_files.py::test_a_byte_order_mark_picks_the_codec_and_is_kept` |
| M08 | `_binary.py` | CR counted as printable | `tests/test_binary.py::test_cr_and_lf_count_for_nothing` |
| M09 | `_kinds.py` | NEL dropped from the unicode set | `src/eolnorm/_eol.py::eolnorm._eol.counts` |
| M10 | `_kinds.py` | RS dropped from the splitlines set | `tests/test_boundaries.py::test_splitlines_set_is_what_the_interpreter_splits_on` |
| M11 | `_kinds.py` | bytes: CR of CRLF counted as lone CR | `src/eolnorm/_files.py::eolnorm._files.scan_file` |
| M12 | `_kinds.py` | text: LF of CRLF counted as lone LF | `src/eolnorm/__init__.py::eolnorm.Normalizer.counts` |
| M13 | `_kinds.py` | CRLF matched as two endings | `src/eolnorm/_eol.py::eolnorm._eol.normalize` |
| M14 | `_kinds.py` | bytes ignore keep_lone_cr | `src/eolnorm/_eol.py::eolnorm._eol.normalize` |
| M15 | `_kinds.py` | text ignores keep_lone_cr | `tests/test_cli.py::test_options_reach_the_library` |
| M16 | `_kinds.py` | kind order swapped | `src/eolnorm/__init__.py::eolnorm.Normalizer.counts` |
| M17 | `_kinds.py` | cr style writes LF | `tests/test_eol.py::test_normalize_to_cr` |
| M18 | `_eol.py` | bytes accepted with the unicode set | `tests/test_eol.py::test_bytes_refuse_the_unicode_sets` |
| M19 | `_eol.py` | mixed reported as one kind | `src/eolnorm/__init__.py::eolnorm.Normalizer.detected` |
| M20 | `_eol.py` | keep_lone_cr dropped for bytes in convert | `src/eolnorm/_eol.py::eolnorm._eol.normalize` |
| M21 | `_eol.py` | keep_lone_cr not type checked | `tests/test_eol.py::test_keep_lone_cr_must_be_a_bool` |
| M22 | `_stream.py` | final does not release a held CR | `src/eolnorm/__init__.py::eolnorm.Normalizer` |
| M23 | `_stream.py` | no CR held across chunks | `src/eolnorm/__init__.py::eolnorm.Normalizer` |
| M24 | `_stream.py` | str and bytes chunks mixed | `tests/test_errors.py::test_mixing_chunk_types_names_the_stream_type` |
| M25 | `_stream.py` | counts property not a copy | `tests/test_stream.py::test_counts_property_is_a_copy` |
| M26 | `_stream.py` | counts not accumulated | `tests/test_docs.py::test_each_example_prints_what_its_comments_say` |
| M27 | `_stream.py` | stream accepts bytes with a unicode set | `tests/test_errors.py::test_bytes_with_a_unicode_set_name_the_set_only` |
| M28 | `_checks.py` | messages quote 400 characters | `src/eolnorm/_checks.py::eolnorm._checks.shown` |
| M29 | `_checks.py` | ints accepted as flags | `src/eolnorm/_checks.py::eolnorm._checks.flag` |
| M30 | `_checks.py` | str subclass passed through | `src/eolnorm/_checks.py::eolnorm._checks.plain` |
| M31 | `_checks.py` | case-insensitive options | `src/eolnorm/_checks.py::eolnorm._checks.option` |
| M32 | `_content.py` | non-text codecs accepted | `tests/test_errors.py::test_codecs_that_are_not_text_encodings_are_refused` |
| M33 | `_content.py` | named codec honours any mark | `tests/test_files.py::test_a_non_utf_encoding_ignores_mark_lookalikes` |
| M34 | `_content.py` | utf-32 without a mark accepted | survived; killed after `tests/test_files.py::test_generic_utf_codec_without_a_mark_needs_a_byte_order[utf-32]` was added |
| M35 | `_content.py` | UTF-16 text called binary | `src/eolnorm/_files.py::eolnorm._files.normalize_file` |
| M36 | `_content.py` | UTF-8 mark written twice | `tests/test_files.py::test_a_byte_order_mark_picks_the_codec_and_is_kept` |
| M37 | `_content.py` | decode error positions after the mark | `tests/test_files_rules.py::test_decoding_error_positions_count_from_the_start_of_the_file` |
| M38 | `_content.py` | round-trip guard removed | `tests/test_files_rules.py::test_normalize_file_refuses_a_codec_that_does_not_give_back_the_bytes` |
| M39 | `_content.py` | utf-8-sig adds a mark | `tests/test_cli.py::test_dash_never_adds_a_mark` |
| M40 | `_files.py` | dry_run writes | `tests/test_atomic.py::test_a_read_only_file_is_refused_on_every_system` |
| M41 | `_files.py` | unchanged files rewritten | `tests/test_atomic.py::test_an_unchanged_file_is_not_rewritten` |
| M42 | `_files.py` | special files read | `tests/test_files_rules.py::test_a_special_file_is_refused_before_it_is_read` |
| M43 | `_files.py` | bom never reported | `src/eolnorm/_files.py::eolnorm._files.normalize_file` |
| M44 | `_files.py` | dry_run not type checked | `tests/test_errors.py::test_file_options_are_checked_before_the_path_is_read` |
| M45 | `_atomic.py` | read-only files rewritten | `tests/test_atomic.py::test_a_read_only_file_is_refused_on_every_system` |
| M46 | `_cli.py` | exit 1 without --check | `tests/test_cli.py::test_fix_rewrites_and_names_each_changed_file` |
| M47 | `_cli.py` | failed path exits 1 | `tests/test_cli.py::test_a_bad_file_exits_two_but_the_rest_still_run` |
| M48 | `_cli.py` | binary line changed | `tests/test_cli.py::test_fix_rewrites_and_names_each_changed_file` |
| M49 | `_cli.py` | filter accepts --check | `tests/test_cli.py::test_usage_errors_exit_two` |
| M50 | `_cli.py` | zero counts printed | `tests/test_cli.py::test_report_names_the_style_and_counts` |
| M51 | `_cli_io.py` | command line messages not cut | `tests/test_cli_streams.py::test_usage_errors_are_cut_short` |
| M52 | `_cli_io.py` | stdout failure not reported in the exit | `tests/test_cli_streams.py::test_any_other_output_failure_is_reported_once_and_exits_two` |
| M53 | `_cli_io.py` | a reader leaving counts as failure | `tests/test_cli_streams.py::test_a_reader_that_leaves_silences_output_but_not_the_work` |

## Packaging, e2e and Pythons (items 8, 10, 13, 14)

- `tests/test_e2e_wheel.py` (with `EOLNORM_E2E=1`) builds the wheel, installs it into a
  fresh venv, runs a consumer program from an empty folder with `-I` (every public name,
  a UTF-16 file rewrite, errors) and drives the `eolnorm` script and `python -m eolnorm`
  by subprocess (report, `--check` exit 1, fix, standard input filter). It also builds the
  sdist and checks both archives: LICENSE, README, GUIDE, CHANGELOG and `py.typed` present,
  only the manifest of the fetched sources, no report or scratch files, only the package
  modules in the wheel, the licence in `.dist-info/licenses`, Production/Stable and no
  runtime dependency in the metadata. Passed on another machine from a fresh clone of
  184f747 together with the full suite.
- Contents listed by hand at 67fc3a7: the sdist holds the sources, tests, scripts, docs,
  `.gitattributes`, `.gitignore`, `.github/FUNDING.yml` and `tests/upstream/MANIFEST.json`;
  the wheel holds the 12 modules, `py.typed`, LICENSE and the metadata. No third-party data
  is shipped.
- Every CPython on this PC from `requires-python` up, at 67fc3a7: wheel and sdist built
  from a fresh clone, `twine check --strict` PASSED for both, the wheel installed in a fresh
  venv with pytest, mypy and `eolify` 0.1.7 (no free-threaded wheel of it exists), and the
  sdist's own suite run against the install with `src` removed and the fetched sources in
  place: 3.10.19 and 3.11.5 305 passed, 5 skipped; 3.12.12, 3.13.2 and 3.14.2 306 passed,
  4 skipped; 3.14.2 free-threaded 302 passed, 5 skipped. Skips: the two build tests (run
  above), POSIX permission bits, named pipes (POSIX), the buffer protocol test (3.12+), and
  `eolify` on 3.14t. 3.13t is not installed here; 3.8 and 3.9 are below `requires-python`.
- PyPI has no eolnorm release, so there is no upgrade path to test.

## Gates (item 15)

Fresh clone of 6d444ee on another machine, CPython 3.14.2, fetched sources, git and `eolify`
0.1.7 present, `EOLNORM_E2E=1`: `ruff format --check .` (42 files), `ruff check .` and
`mypy --strict src tests` (35 files) exit 0; `pytest` 326 passed, 2 skipped (POSIX
permission bits, named pipes), doctests included. The commit after it only fills in this
paragraph.
