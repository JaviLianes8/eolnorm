"""Command line tool: report line endings, check them, or fix them in place."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from ._cli_io import Output, Parser, reason
from ._content import check_encoding, decode, fix
from ._files import FileReport, normalize_file, scan_file


def _parser() -> Parser:
    from . import __version__

    parser = Parser(
        prog="eolnorm",
        description="Report line endings, or convert them with --to. "
        "Use - to filter standard input to standard output.",
    )
    parser.add_argument("paths", nargs="+", metavar="PATH")
    parser.add_argument("--to", choices=["lf", "crlf", "cr"], help="convert to this style")
    parser.add_argument(
        "--check", action="store_true", help="with --to, change nothing; exit 1 if a file would"
    )
    parser.add_argument(
        "--keep-lone-cr", action="store_true", help="leave a CR not followed by LF alone"
    )
    parser.add_argument("--breaks", choices=["ascii", "unicode", "splitlines"], default="ascii")
    parser.add_argument(
        "--encoding", help="decode with this codec (binary files are still skipped)"
    )
    parser.add_argument("--version", action="version", version=f"eolnorm {__version__}")
    return parser


def _describe(report: FileReport) -> str:
    if report.binary:
        return f"{report.path}: binary"
    present = ", ".join(f"{name}={count}" for name, count in report.counts.items() if count)
    return f"{report.path}: {report.detected}" + (f" ({present})" if present else "")


def _filter(args: argparse.Namespace, out: Output) -> int:
    # The same rules as for files: a byte order mark picks and keeps the codec, binary
    # input passes through untouched.
    source = getattr(sys.stdin, "buffer", None)
    for stream, what in ((source, "input"), (sys.stdout, "output")):
        if stream is None:
            out.note(f"eolnorm: -: standard {what} is closed")
            return 2
    try:
        content = decode(source.read(), args.breaks, args.encoding)  # type: ignore[union-attr]
        data = fix(content, args.to, args.breaks, args.keep_lone_cr)
    except (OSError, ValueError) as error:
        out.note(f"eolnorm: -: {reason(error)}")
        return 2
    if content.body is None:
        out.note("eolnorm: -: binary, passed through unchanged")
    out.data(data)
    return 0


def _one(path: str, args: argparse.Namespace, out: Output) -> bool:
    """Handle one path; return True when it was or would be changed."""
    if args.to is None:
        out.line(_describe(scan_file(path, breaks=args.breaks, encoding=args.encoding)))
        return False
    report = normalize_file(
        path,
        args.to,
        breaks=args.breaks,
        keep_lone_cr=args.keep_lone_cr,
        encoding=args.encoding,
        dry_run=args.check,
    )
    if report.binary:
        out.line(f"skipped {path}: binary")
    elif report.changed:
        out.line(f"{'would fix' if args.check else 'fixed'} {path}")
    return report.changed


def _run(argv: Sequence[str] | None, out: Output) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    for flag, used in (("--check", args.check), ("--keep-lone-cr", args.keep_lone_cr)):
        if used and args.to is None:
            parser.error(f"{flag} needs --to")
    if "-" in args.paths and (args.to is None or args.check or len(args.paths) > 1):
        parser.error("- filters standard input and needs --to, alone, without --check")
    try:
        args.encoding = check_encoding(args.encoding)
    except ValueError as error:
        parser.error(str(error))
    if args.paths == ["-"]:
        return _filter(args, out)
    failed = pending = False
    for path in args.paths:
        try:
            pending |= _one(path, args, out)
        except (OSError, ValueError) as error:
            out.note(f"eolnorm: {path}: {reason(error)}")
            failed = True
    if failed:
        return 2
    return 1 if pending and args.check else 0


def main(argv: Sequence[str] | None = None) -> int:
    """Run the tool. Exit 0 on success, 1 when --check finds work, 2 on bad input.

    Exit 2 also covers a failure to write standard output; a reader that goes away
    early (``eolnorm ... | head``) is not a failure and only silences the output.
    """
    out = Output()
    try:
        code = _run(argv, out)
    except SystemExit:  # help, version and usage errors, already written
        out.finish(0)
        raise
    return out.finish(code)
