# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.0.0] - 2026-10-19

The public API is now stable: `counts`, `detect`, `normalize`, `Normalizer`, `is_binary`,
`scan_file`, `normalize_file`, `FileReport` and the `Style`, `Kind`, `Detected` and `Breaks`
aliases keep their names, parameters, defaults, results and error types until 2.0.0, and so
do the `eolnorm` command's options, output lines and exit codes.

### Added

- `GUIDE.md`: every public name in detail, the errors each one raises and the command line
  contract, with examples that run as tests.

### Changed

- A `to` or `breaks` value that is not a string raises `TypeError` (it was `ValueError`);
  an unknown string still raises `ValueError`.
- `dry_run` and `Normalizer.feed(final=...)` must be `bool`, like `keep_lone_cr`: any other
  value raises `TypeError` instead of being read as true or false.
- `encoding=` accepts text encodings only: a codec such as `hex`, `base64`, `rot13` or `zlib`
  raises `ValueError` up front instead of `LookupError` from the decoder. On the command line
  an unknown or unusable `--encoding` is a usage error (exit 2, before any file is read).
- `normalize_file` refuses a codec that does not give back the file's bytes from the decoded
  text (UTF-7, `unicode_escape`, duplicate mappings of CJK codecs such as cp932): it raises
  `ValueError` and writes nothing, also in a dry run, where 0.2.0 rewrote more than line
  endings. `scan_file` still reports such files.
- The binary check also runs after a UTF-8 byte order mark (on the whole file, mark
  included, as git counts it): such a file with NUL or control bytes is reported binary and
  left alone.
- An explicit `encoding=` always decodes the file, so a file that is not valid in that codec
  raises `UnicodeDecodeError` even after a UTF-8 mark.
- `UnicodeDecodeError` positions count from the start of the file, byte order mark included.
- `scan_file` and `normalize_file` read regular files only: a directory raises
  `IsADirectoryError` on every system (it was `PermissionError` on Windows) and a pipe, socket
  or device raises `shutil.SpecialFileError` (an `OSError`) instead of being read. The check
  is made again on the opened file, which is opened without waiting for a pipe's writer, so
  a path swapped in between is refused too. A `path` that is neither a `str` nor an
  `os.PathLike[str]` raises `TypeError`.
- Error messages quote at most 40 characters of an argument and of a type name.
- A `str` or `bytes` subclass is read through the base type, so none of its methods runs,
  and the results are plain `str` or `bytes`; an object that only claims to be a string
  through `__class__` is refused.
- `FileReport` and `Normalizer` show and pickle as `eolnorm.FileReport` and
  `eolnorm.Normalizer`. A copy of a `Normalizer` keeps its own counts, and `repr` shows its
  options. The package no longer exposes a stray `annotations` name.
- The command line: when its reader goes away (`eolnorm ... | head`) it stops writing
  quietly, still processes every path and exits with the status the work earned (0.2.0
  reported every later line as a failure of the file and exited 120); any other failure to
  write standard output is reported and exits 2, a closed standard output included once
  there is something to write (0.2.0 dropped the report and exited 0). A closed standard
  input gives exit 2 with a
  message instead of a traceback. Error lines name the path once, usage errors are cut at
  300 characters, and `python -m eolnorm` only runs the tool when executed.

## [0.2.0] - 2026-10-13

### Added

- `breaks=` on every function: `"unicode"` adds the UAX #14 mandatory breaks (VT, FF, NEL,
  LS, PS) and `"splitlines"` adds the three information separators, matching
  `str.splitlines`. `Kind` and `Breaks` name the endings and the sets.
- `counts`, `detect` and `normalize` accept `bytes` (ASCII set) and return the same type.
- `keep_lone_cr=True` leaves a CR that is not followed by LF alone, as git does for paths
  with the `text` attribute.
- `Normalizer` for streams: a CRLF split across chunks stays one ending; running counts.
- `is_binary`, using git's text=auto statistics.
- `scan_file` and `normalize_file` with `FileReport`: byte order marks (UTF-8, UTF-16,
  UTF-32) are detected and kept, an explicit `encoding` covers other codecs, binary files
  are skipped, and the rewrite is atomic (temporary file, fsync, mode kept, one rename,
  symlinks followed, read-only files refused). `dry_run=True` only reports.
- The `eolnorm` command (also `python -m eolnorm`) with `--to`, `--check`, `--keep-lone-cr`,
  `--breaks`, `--encoding` and `-` for standard input, which follows the same byte order
  mark and binary rules as files.

### Changed

- `Detected` also covers the new kinds. `to` and `breaks` values are checked up front with
  a clear `ValueError`, and a value that is neither `str` nor `bytes` raises `TypeError`.

## [0.1.0] - 2026-10-11

- First version: `detect`, `normalize` and `counts` for line endings in text, with CRLF
  treated as a single unit.
