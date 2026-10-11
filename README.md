# eolnorm

Detect, normalize and count line endings in text

## Install

```
pip install eolnorm
```

## Usage

```python
from eolnorm import detect, normalize, counts

detect("a\nb\nc")        # "lf"
detect("a\r\nb\r\n")     # "crlf"
detect("a\rb\rc")        # "cr"
detect("a\nb\r\nc")      # "mixed"
detect("single line")    # "none"

normalize("a\r\nb\rc\n", to="lf")    # "a\nb\nc\n"
normalize("a\nb", to="crlf")         # "a\r\nb"

counts("a\r\nb\r\nc\n")  # {"lf": 1, "crlf": 2, "cr": 0}
```

CRLF counts as one ending, never as a CR plus an LF, and `normalize` rewrites a lone
CR as well.

## Why

The standard library only resolves line endings while decoding a file in universal
newline mode. There is no helper to inspect, convert or tally the endings of a string
already in memory. `eolnorm` fills that gap with three small typed functions and no
dependencies. Existing options fall short: `eolify` is a compiled Rust extension that
only converts, with no detection and no counts.

## License

MIT. See [LICENSE](LICENSE).

## Links

- Website: https://lianes8studio.com
- GitHub: https://github.com/JaviLianes8
- LinkedIn: https://www.linkedin.com/in/jlianes/
