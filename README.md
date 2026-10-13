# eolnorm

Detect, normalize and count line endings in text, bytes, streams and files. It can match
git's `text` conversion byte for byte, knows the Unicode line boundaries, rewrites files
atomically, and has no dependencies.

## Install

```
pip install eolnorm
```

## Usage

```python
from eolnorm import counts, detect, normalize

print(detect("a\r\nb\r\n"))
# crlf
print(detect("a\nb\r\n"))
# mixed
print(repr(normalize("a\r\nb\rc\n")))
# 'a\nb\nc\n'
print(counts("a\r\nb\r\nc\n"))
# {'lf': 1, 'crlf': 2, 'cr': 0}
```

`detect` returns a `Detected` value: the single kind present, `"mixed"` or `"none"`.
`normalize` converts to a `Style` (`"lf"`, the default, `"crlf"` or `"cr"`). CRLF is always
one ending, never a CR plus an LF.

### Bytes, and what git stores

```python
from eolnorm import normalize

print(normalize(b"caf\xe9\r\nold\rmac\n"))
# b'caf\xe9\nold\nmac\n'
print(normalize(b"a\rb\r\n", keep_lone_cr=True))
# b'a\rb\n'
```

`bytes` in, `bytes` out: CR and LF are the same bytes in every ASCII-compatible encoding
(UTF-8, latin-1, cp1252 and so on), so nothing is decoded and every other byte is kept.

`keep_lone_cr=True` leaves a CR that is not followed by LF alone. That is exactly what git
does for a path with the `text` attribute: `normalize(data, "lf", keep_lone_cr=True)` is
the blob `git add` stores under `text eol=lf`, and `normalize(blob, "crlf",
keep_lone_cr=True)` is the file `git checkout` writes under `eol=crlf`. The test suite runs
the installed git on hundreds of samples to prove it.

### Unicode line boundaries

```python
from eolnorm import counts, detect, normalize

text = "page one\x0cpage two\x85end"
print(detect(text))
# none
print(detect(text, breaks="unicode"))
# mixed
print(repr(normalize(text, "lf", breaks="unicode")))
# 'page one\npage two\nend'
print(counts("a\x1eb", breaks="splitlines")["rs"])
# 1
```

`breaks` picks the boundary set (a `Breaks` value). Each recognised ending has a `Kind` name.

| `breaks` | Endings | Same as |
| --- | --- | --- |
| `"ascii"` (default) | `lf`, `crlf`, `cr` | universal newlines |
| `"unicode"` | adds `vt`, `ff`, `nel` (U+0085), `ls` (U+2028), `ps` (U+2029) | UAX #14 mandatory breaks (classes BK, CR, LF, NL) |
| `"splitlines"` | adds `fs`, `gs`, `rs` (U+001C to U+001E) | `str.splitlines` |

`counts` always returns every kind of the chosen set, in that order. The two Unicode sets
need decoded text: passing `bytes` with them raises `ValueError`. Note that they convert form
feeds and vertical tabs too, so page breaks in `^L`-paginated sources become newlines; keep
the default set for such files.

### Streams

```python
from eolnorm import Normalizer

stream = Normalizer("lf")
out = stream.feed(b"one\r") + stream.feed(b"\ntwo\r") + stream.feed(b"", final=True)
print(out)
# b'one\ntwo\n'
print(stream.counts, stream.detected)
# {'lf': 0, 'crlf': 1, 'cr': 1} mixed
```

`Normalizer` takes the same options as `normalize`. A chunk ending in CR is held back until
the next chunk shows whether an LF follows, so a CRLF split across two reads is still one
ending. Pass `final=True` with the last chunk. All chunks of one stream are `str` or all are
`bytes`.

### Files

```python
import codecs
import tempfile
from pathlib import Path

from eolnorm import is_binary, normalize_file, scan_file

path = Path(tempfile.mkdtemp()) / "notes.txt"
path.write_bytes(codecs.BOM_UTF16_LE + "one\r\ntwo\r\n".encode("utf-16-le"))
report = normalize_file(path, "lf")
print(report.encoding, report.bom, report.detected, report.changed)
# utf-16-le True crlf True
print(scan_file(path).detected)
# lf
print(normalize_file(path, "crlf", dry_run=True).changed)
# True
print(is_binary(b"\x89PNG\r\n\x1a\n\x00"))
# True
```

`normalize_file` and `scan_file` return a `FileReport` (`path`, `binary`, `encoding`, `bom`,
`counts`, `detected`, `changed`; the counts describe the file before any change).

- A UTF-8, UTF-16 or UTF-32 byte order mark selects the codec, and the same mark is written
  back. Without a mark the bytes are handled undecoded (ASCII set) or as UTF-8 (Unicode
  sets). `encoding=` names a codec instead, for example `"utf-16-le"` for a file without a
  mark. A named UTF codec still honours its own marks; generic `"utf-16"` and `"utf-32"`
  without a mark are refused because the byte order is unknown. Any other codec (say
  `"cp1252"`) decodes every byte as text, even bytes that look like a mark.
- Binary files are reported and never changed. `is_binary` uses git's text=auto
  statistics: a NUL byte, or fewer than 128 printable bytes per control byte, means binary.
  Git also treats a lone CR as binary; `is_binary` does not, so old Mac files can be fixed.
  The check also runs with an explicit ASCII-compatible `encoding`; it is skipped only for
  codecs such as UTF-16, whose text is full of NUL bytes.
- The rewrite is atomic: the new bytes go to a temporary file in the same folder, are
  flushed to disk, get the original's permission bits, and replace the original in one
  rename. A symlink is followed and stays a symlink. A file whose bytes would not change
  is not touched, and `dry_run=True` only reports. A read-only file is refused with
  `PermissionError` on every system. Being a new file, the result does not keep hard links,
  the owner and group, or Windows attributes and access lists of the original.

### Command line

```
$ eolnorm notes.txt logo.png
notes.txt: crlf (crlf=2)
logo.png: binary
$ eolnorm --to lf --check notes.txt
would fix notes.txt
$ eolnorm --to lf notes.txt
fixed notes.txt
$ eolnorm --to crlf - < in.txt > out.txt
```

Options: `--to {lf,crlf,cr}`, `--check` (with `--to`: write nothing, exit 1 if a file would
change, handy in a pre-commit hook), `--keep-lone-cr`, `--breaks {ascii,unicode,splitlines}`
and `--encoding`. `-` filters standard input to standard output with the same rules as for
files (a byte order mark is kept, binary input passes through unchanged). Exit code 2 means bad
usage or a file that could not be read or decoded; the other files are still processed.
`python -m eolnorm` works too.

## Why

The standard library resolves line endings only while decoding a file in universal newline
mode. There is no helper to inspect, convert or count the endings of data already in
memory, to do it on bytes without decoding, to match git's rules, or to fix a file in
place safely. `eolify` is a compiled extension focused on fast conversion; `eolnorm` is pure
Python and covers detection, counting, Unicode boundaries, streams and files.

## License

MIT. See [LICENSE](LICENSE).

## Links

- Website: https://lianes8studio.com
- GitHub: https://github.com/JaviLianes8
- LinkedIn: https://www.linkedin.com/in/jlianes/
