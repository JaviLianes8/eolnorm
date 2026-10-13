# Changelog

All notable changes to this project are documented here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the project uses
[Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0]

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
  symlinks followed). `dry_run=True` only reports.
- The `eolnorm` command (also `python -m eolnorm`) with `--to`, `--check`, `--keep-lone-cr`,
  `--breaks`, `--encoding` and `-` for standard input.

### Changed

- `Detected` also covers the new kinds. `to` and `breaks` values are checked up front with
  a clear `ValueError`, and a value that is neither `str` nor `bytes` raises `TypeError`.

## [0.1.0]

- First release: `detect`, `normalize` and `counts` for line endings in text, with CRLF
  treated as a single unit.
