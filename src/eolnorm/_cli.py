"""Command line tool: report line endings, check them, or fix them in place."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from ._eol import normalize
from ._files import FileReport, normalize_file, scan_file


def _parser() -> argparse.ArgumentParser:
    from . import __version__

    parser = argparse.ArgumentParser(
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
    parser.add_argument("--encoding", help="decode files with this codec")
    parser.add_argument("--version", action="version", version=f"eolnorm {__version__}")
    return parser


def _describe(report: FileReport) -> str:
    if report.binary:
        return f"{report.path}: binary"
    present = ", ".join(f"{name}={count}" for name, count in report.counts.items() if count)
    return f"{report.path}: {report.detected}" + (f" ({present})" if present else "")


def _filter(args: argparse.Namespace) -> None:
    data = sys.stdin.buffer.read()
    if args.encoding is None and args.breaks == "ascii":
        result = normalize(data, args.to, keep_lone_cr=args.keep_lone_cr)
    else:
        codec = args.encoding or "utf-8"
        text = normalize(
            data.decode(codec), args.to, breaks=args.breaks, keep_lone_cr=args.keep_lone_cr
        )
        result = text.encode(codec)
    sys.stdout.buffer.write(result)
    sys.stdout.flush()


def _one(path: str, args: argparse.Namespace) -> bool:
    """Handle one path; return True when it was or would be changed."""
    if args.to is None:
        print(_describe(scan_file(path, breaks=args.breaks, encoding=args.encoding)))
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
        print(f"skipped {path}: binary")
    elif report.changed:
        print(f"{'would fix' if args.check else 'fixed'} {path}")
    return report.changed


def main(argv: Sequence[str] | None = None) -> int:
    """Run the tool. Exit 0 on success, 1 when --check finds work, 2 on bad input."""
    args = _parser().parse_args(argv)
    if args.check and args.to is None:
        _parser().error("--check needs --to")
    if "-" in args.paths:
        if args.to is None or args.check or len(args.paths) > 1:
            _parser().error("- filters standard input and needs --to, alone, without --check")
        try:
            _filter(args)
        except (UnicodeError, LookupError) as error:
            print(f"eolnorm: -: {error}", file=sys.stderr)
            return 2
        return 0
    failed = pending = False
    for path in args.paths:
        try:
            pending |= _one(path, args)
        except (OSError, UnicodeError, ValueError) as error:
            print(f"eolnorm: {path}: {error}", file=sys.stderr)
            failed = True
    if failed:
        return 2
    return 1 if pending and args.check else 0
