"""Command line tool: report line endings, check them, or fix them in place."""

from __future__ import annotations

import argparse
import sys
from collections.abc import Sequence

from ._content import decode, fix
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


def _filter(args: argparse.Namespace) -> None:
    # The same rules as for files: a byte order mark picks and keeps the codec, binary
    # input passes through untouched.
    content = decode(sys.stdin.buffer.read(), args.breaks, args.encoding)
    if content.body is None:
        print("eolnorm: -: binary, passed through unchanged", file=sys.stderr)
    sys.stdout.buffer.write(fix(content, args.to, args.breaks, args.keep_lone_cr))
    sys.stdout.flush()


def _readable(stream: object) -> None:
    # A path the console cannot encode must not turn a finished fix into a reported failure.
    reconfigure = getattr(stream, "reconfigure", None)
    if reconfigure is not None:
        reconfigure(errors="backslashreplace")


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
    for flag, used in (("--check", args.check), ("--keep-lone-cr", args.keep_lone_cr)):
        if used and args.to is None:
            _parser().error(f"{flag} needs --to")
    _readable(sys.stdout)
    _readable(sys.stderr)
    if "-" in args.paths:
        if args.to is None or args.check or len(args.paths) > 1:
            _parser().error("- filters standard input and needs --to, alone, without --check")
        try:
            _filter(args)
        except ValueError as error:
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
