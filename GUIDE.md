# eolnorm guide

The behaviour of every public name in detail, the errors each one raises, and the command
line contract. Each Python block below runs as a test: a comment line after a `print`
holds what it prints.

## Names for the strings

Four `typing.Literal` aliases name the strings the functions take and return, so a type
checker catches a misspelt option:

- `Style`: `"lf"`, `"crlf"` or `"cr"`, the target of `normalize`, `Normalizer` and
  `normalize_file`.
- `Breaks`: `"ascii"`, `"unicode"` or `"splitlines"`, a boundary set.
- `Kind`: the name of one ending, a key of the dict `counts` returns.
- `Detected`: what `detect` returns, a `Kind`, `"mixed"` or `"none"`.

## Boundary sets

Every function but `is_binary` takes `breaks=`, a `Breaks` value naming which characters
end a line. CRLF is one ending in every set, never a CR plus an LF.

| `breaks` | Kinds, in report order | Checked against |
| --- | --- | --- |
| `"ascii"` (default) | `lf`, `crlf`, `cr` | the universal newlines of the CPython glossary, `io` and `open` docs, and the running interpreter's `io` module |
| `"unicode"` | `lf`, `crlf`, `cr`, `vt`, `ff`, `nel`, `ls`, `ps` | UAX #14 rules LB4 and LB5 (classes BK, CR, LF, NL) and their code points in `LineBreak.txt` 18.0.0 |
| `"splitlines"` | `lf`, `crlf`, `cr`, `vt`, `ff`, `fs`, `gs`, `rs`, `nel`, `ls`, `ps` | the `str.splitlines` table and every code point asked of the running interpreter |

The two Unicode sets need decoded text; with `bytes` they raise `ValueError`.

```python
from eolnorm import counts, normalize

print(counts("a\x0bb\x1cc", breaks="splitlines"))
# {'lf': 0, 'crlf': 0, 'cr': 0, 'vt': 1, 'ff': 0, 'fs': 1, 'gs': 0, 'rs': 0, 'nel': 0, 'ls': 0, 'ps': 0}
print(repr(normalize("a\x0bb\x1cc", "crlf", breaks="unicode")))
# 'a\r\nb\x1cc'
```

## Text and bytes

`normalize`, `counts` and `detect` take `str` or `bytes`, and `normalize` gives back the
type it was given. Anything else (`bytearray`, `memoryview`, a path) raises `TypeError`. A
`str` or `bytes` subclass is read through the base type, so none of its own methods runs,
and the result is a plain `str` or `bytes`.

`bytes` are never decoded: CR and LF are the same bytes in every ASCII-compatible encoding,
so every other byte is kept as it was. UTF-16 and UTF-32 data must be decoded first, or
handled by the file functions, which read their byte order marks.

`keep_lone_cr=True` matches git's `text` conversion: only a CR followed by LF is an ending,
and a lone CR is left alone, in `normalize`, `Normalizer` and `normalize_file`. `counts`
still counts a lone CR as `cr`. The rule is the one of `crlf_to_git` and
`crlf_to_worktree` in git's `convert.c`, and the test suite compares it with the installed
git on random samples.

```python
from eolnorm import detect, normalize

print(normalize(b"a\rb\r\n", "crlf", keep_lone_cr=True))
# b'a\rb\r\n'
print(detect("a\rb\r\n"), detect(""))
# mixed none
```

## Streams

`Normalizer(to, *, breaks, keep_lone_cr)` takes the options of `normalize`. `feed(chunk,
final=False)` returns the output that is safe to emit: a chunk ending in CR keeps that CR
back until the next chunk shows whether an LF follows. Feeding the whole input in any
number of pieces, the last with `final=True`, gives exactly what `normalize` gives on the
whole. `counts` and `detected` cover what was fed so far, a held CR not yet included;
`counts` is a new dict on each read. The first chunk fixes the stream's type: a chunk of
the other type raises `TypeError` and leaves the stream as it was. A `Normalizer` can be
copied and pickled; a copy keeps its own counts.

```python
from eolnorm import Normalizer

stream = Normalizer("crlf")
print(repr(stream.feed("one\r")), repr(stream.feed("\ntwo\r", final=True)))
# 'one' '\r\ntwo\r\n'
print(stream.counts)
# {'lf': 0, 'crlf': 1, 'cr': 1}
```

## Binary data

`is_binary(data)` takes `bytes` and applies the statistics of git's `gather_stats` and
`convert_is_binary` (read from `convert.c` of git 2.54.0): a NUL byte, or fewer than 128
printable bytes for each non-printable one, means binary. DEL and the control bytes below
0x20 are non-printable, except BS, HT, ESC and FF, which are printable, and CR and LF, which
count for nothing. Bytes from 0x80 up are printable, and a Ctrl-Z as the very last byte is
not held against the data. Git also calls any data with a lone CR binary; `is_binary` does
not, so files from classic Mac OS can be fixed.

## Files

`scan_file(path, *, breaks, encoding)` reports, `normalize_file(path, to, *, breaks,
keep_lone_cr, encoding, dry_run)` rewrites. Both read regular files only and return a
`FileReport`:

| Field | Meaning |
| --- | --- |
| `path` | the path as given, as a `str` |
| `binary` | the file looked binary and was left alone (all counts are zero) |
| `encoding` | the codec that decoded the file, as `codecs.lookup` spells it, or `None` when the bytes were handled undecoded |
| `bom` | a byte order mark was found and kept |
| `counts`, `detected` | the endings before any change, as `counts` and `detect` report them |
| `changed` | the bytes changed, or would have with `dry_run=True`; always `False` from `scan_file` |

How the codec is chosen:

- A UTF-8, UTF-16 or UTF-32 byte order mark picks the codec, and the same mark is written
  back. The rest of the file is always decoded with that codec, so bytes that are not valid
  in it raise `UnicodeDecodeError` whatever the options. `encoding` reports the codec of the
  mark: `"utf-8"` for a UTF-8 mark (also when `"utf-8-sig"` was named), `"utf-16-le"` or
  `"utf-16-be"` when `"utf-16"` was named, and so on; `bom` says whether a mark was there.
- Without a mark and without `encoding=`, the ASCII set works on the undecoded bytes
  (`encoding` is `None`) and the Unicode sets decode UTF-8.
- `encoding=` names any text codec. A UTF codec still recognises its own marks; plain
  `"utf-16"` or `"utf-32"` without a mark raises `ValueError`, since the byte order is
  unknown. Other codecs decode every byte as text.
- The binary check runs on the raw bytes, mark included, for every ASCII-compatible codec;
  it is skipped for codecs that are not, such as UTF-16 and UTF-32, whose text is full of
  NUL bytes.
- A codec that does not give back the file's bytes from the decoded text (UTF-7, for
  instance) is refused by `normalize_file` with `ValueError`, so nothing but line endings
  ever changes.

The rewrite is atomic: the new bytes go to a temporary file in the same folder, are flushed
to disk, get the permission bits of the original and replace it in one rename. A symlink is
followed and stays a symlink. Unchanged bytes are never rewritten, and `dry_run=True` never
writes. The result is a new file, so hard links, owner, group and Windows attributes and
access lists of the original are not kept.

## Errors

Arguments are checked before any file is read or any output produced. A `TypeError` or
`ValueError` about an argument quotes at most 40 characters of the value or of a type name.
An `OSError` follows the system's convention instead: the path is in its `filename`
attribute and in its message, whole, as in the errors the system raises itself.

| Raised | When |
| --- | --- |
| `TypeError` | input that is not `str` or `bytes` (`is_binary`: not `bytes`); `to`, `breaks` or `encoding` of the wrong type; `keep_lone_cr`, `dry_run` or `final` that is not a `bool`; a `path` that is not a `str` or `os.PathLike[str]`; a chunk whose type differs from the stream's |
| `ValueError` | an unknown style, boundary set or text encoding; `bytes` with a Unicode set; `"utf-16"` or `"utf-32"` without a mark; a codec that would change more than line endings; a path with a NUL character |
| `UnicodeDecodeError` | a file that is not valid in its codec; positions count from the start of the file |
| `FileNotFoundError`, `PermissionError` and other `OSError` | as the system reports them; a read-only file is refused with `PermissionError` on every system |
| `IsADirectoryError` | a directory, on every system |
| `shutil.SpecialFileError` | a pipe, socket or device (it is an `OSError`) |

```python
from eolnorm import normalize

try:
    normalize("text", "x" * 1000)
except ValueError as error:
    print(len(str(error)) < 70)
# True
try:
    normalize(bytearray(b"a"))
except TypeError as error:
    print(error)
# expected str or bytes, got bytearray
```

## Command line

`eolnorm PATH...` prints one line per path: `PATH: KIND (kind=count, ...)`, or
`PATH: binary`. With `--to STYLE` it converts and prints `fixed PATH`, `skipped PATH:
binary`, or nothing for a file that needed no change; with `--check` as well it writes
nothing and prints `would fix PATH`. `--keep-lone-cr`, `--breaks` and `--encoding` are the
keyword arguments of the same names. `-` as the only path, with `--to` and without
`--check`, filters standard input to standard output under the same rules as a file.

| Exit | Meaning |
| --- | --- |
| 0 | done |
| 1 | `--check` found a file that would change |
| 2 | bad usage, or a path that could not be read, decoded or written (the other paths are still processed), or standard output could not be written |

Errors go to standard error as `eolnorm: PATH: reason`, with the path and the reason each
cut after 300 characters. Every path the tool prints, on either stream, has its control
characters (C0, DEL, C1, and the line and paragraph separators U+2028 and U+2029) written
as Python escapes such as `\x1b`, so a file name cannot move the cursor, retitle the
terminal or start a line of its own; report lines on standard output keep the path whole
otherwise. A reader that goes away early, as in `eolnorm *.txt | head`, is not an error: the
remaining output is dropped and every path is still processed. `python -m eolnorm` runs the same tool.
