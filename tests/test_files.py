"""scan_file and normalize_file: encodings, byte order marks, binary files, dry runs."""

from __future__ import annotations

import codecs
from pathlib import Path

import pytest

from eolnorm import FileReport, normalize_file, scan_file


def _file(tmp_path: Path, data: bytes, name: str = "f.txt") -> Path:
    path = tmp_path / name
    path.write_bytes(data)
    return path


def test_ascii_compatible_bytes_are_kept_exactly(tmp_path: Path) -> None:
    path = _file(tmp_path, b"caf\xe9\r\nna\xefve\rend\n")
    report = normalize_file(path)
    assert path.read_bytes() == b"caf\xe9\nna\xefve\nend\n"
    assert report == FileReport(
        path=str(path),
        binary=False,
        encoding=None,
        bom=False,
        counts={"lf": 1, "crlf": 1, "cr": 1},
        detected="mixed",
        changed=True,
    )


def test_scan_reports_without_writing(tmp_path: Path) -> None:
    path = _file(tmp_path, b"a\r\nb\r\n")
    report = scan_file(path)
    assert (report.detected, report.changed, report.counts["crlf"]) == ("crlf", False, 2)
    assert path.read_bytes() == b"a\r\nb\r\n"


@pytest.mark.parametrize(
    ("bom", "codec"),
    [
        (codecs.BOM_UTF16_LE, "utf-16-le"),
        (codecs.BOM_UTF16_BE, "utf-16-be"),
        (codecs.BOM_UTF32_LE, "utf-32-le"),
        (codecs.BOM_UTF32_BE, "utf-32-be"),
        (codecs.BOM_UTF8, "utf-8"),
    ],
)
def test_a_byte_order_mark_picks_the_codec_and_is_kept(
    tmp_path: Path, bom: bytes, codec: str
) -> None:
    path = _file(tmp_path, bom + "\u00e9\r\n\u2603\r\n".encode(codec))
    report = normalize_file(path, "lf")
    assert path.read_bytes() == bom + "\u00e9\n\u2603\n".encode(codec)
    assert (report.encoding, report.bom, report.binary) == (codec, True, False)
    assert report.counts["crlf"] == 2


def test_a_utf8_mark_keeps_the_ascii_set_byte_exact(tmp_path: Path) -> None:
    # Not valid UTF-8 after the mark, but the ASCII set never needs to decode it.
    path = _file(tmp_path, codecs.BOM_UTF8 + b"caf\xe9\r\n")
    report = normalize_file(path)
    assert path.read_bytes() == codecs.BOM_UTF8 + b"caf\xe9\n"
    assert (report.encoding, report.bom, report.changed) == ("utf-8", True, True)


def test_utf16_without_a_mark_looks_binary_and_is_left_alone(tmp_path: Path) -> None:
    data = "a\r\nb\r\n".encode("utf-16-le")
    path = _file(tmp_path, data)
    report = normalize_file(path)
    assert (report.binary, report.changed, report.detected) == (True, False, "none")
    assert sum(report.counts.values()) == 0
    assert path.read_bytes() == data


def test_an_explicit_encoding_handles_utf16_without_a_mark(tmp_path: Path) -> None:
    path = _file(tmp_path, "a\r\nb\r\n".encode("utf-16-be"))
    report = normalize_file(path, encoding="UTF-16BE")
    assert path.read_bytes() == "a\nb\n".encode("utf-16-be")
    assert (report.encoding, report.bom, report.binary) == ("utf-16-be", False, False)


def test_generic_utf16_without_a_mark_needs_a_byte_order(tmp_path: Path) -> None:
    path = _file(tmp_path, "a\r\n".encode("utf-16-le"))
    with pytest.raises(ValueError, match="byte order"):
        normalize_file(path, encoding="utf-16")


def test_generic_utf16_with_a_mark_is_accepted(tmp_path: Path) -> None:
    path = _file(tmp_path, codecs.BOM_UTF16_BE + "a\r\n".encode("utf-16-be"))
    normalize_file(path, encoding="utf-16")
    assert path.read_bytes() == codecs.BOM_UTF16_BE + "a\n".encode("utf-16-be")


def test_a_non_utf_encoding_ignores_mark_lookalikes(tmp_path: Path) -> None:
    # Two bytes FF FE at the start of a cp1252 file are text, not a UTF-16 mark.
    path = _file(tmp_path, b"\xff\xfeab\r\n")
    report = normalize_file(path, encoding="cp1252")
    assert path.read_bytes() == b"\xff\xfeab\n"
    assert (report.encoding, report.bom) == ("cp1252", False)


def test_a_named_utf16_codec_is_not_mistaken_for_utf32(tmp_path: Path) -> None:
    data = codecs.BOM_UTF16_LE + "\x00a\r\n".encode("utf-16-le")
    path = _file(tmp_path, data)
    report = normalize_file(path, encoding="utf-16")
    assert path.read_bytes() == codecs.BOM_UTF16_LE + "\x00a\n".encode("utf-16-le")
    assert (report.encoding, report.bom) == ("utf-16-le", True)


def test_an_explicit_ascii_compatible_encoding_still_skips_binary(tmp_path: Path) -> None:
    data = b"\x89PNG\r\n\x1a\n\x00\x00\r\n"
    path = _file(tmp_path, data)
    report = normalize_file(path, encoding="latin-1")
    assert (report.binary, report.changed) == (True, False)
    assert path.read_bytes() == data


def test_reports_are_hashable(tmp_path: Path) -> None:
    report = scan_file(_file(tmp_path, b"a\n"))
    assert hash(report) == hash(scan_file(tmp_path / "f.txt"))
    assert report == scan_file(tmp_path / "f.txt")


def test_utf8_sig_without_a_mark_does_not_add_one(tmp_path: Path) -> None:
    path = _file(tmp_path, b"a\r\n")
    report = normalize_file(path, encoding="utf-8-sig")
    assert path.read_bytes() == b"a\n"
    assert (report.encoding, report.bom) == ("utf-8", False)


def test_unknown_encoding_is_a_value_error(tmp_path: Path) -> None:
    path = _file(tmp_path, b"a\n")
    with pytest.raises(ValueError, match="unknown encoding"):
        scan_file(path, encoding="no-such-codec")
    with pytest.raises(TypeError, match="encoding must be"):
        scan_file(path, encoding=8)  # type: ignore[arg-type]


def test_a_decoding_error_leaves_the_file_untouched(tmp_path: Path) -> None:
    path = _file(tmp_path, b"\xff\xfe\xfd\r\n"[2:] + b"\x80\r\n")
    with pytest.raises(UnicodeDecodeError):
        normalize_file(path, encoding="utf-8")
    assert path.read_bytes() == b"\xfd\r\n\x80\r\n"


def test_unicode_breaks_decode_utf8_by_default(tmp_path: Path) -> None:
    path = _file(tmp_path, "a\u2028b\x85c\r\n".encode())
    report = normalize_file(path, "lf", breaks="unicode")
    assert path.read_bytes() == b"a\nb\nc\n"
    assert (report.encoding, report.detected) == ("utf-8", "mixed")


def test_unicode_breaks_after_a_utf8_mark(tmp_path: Path) -> None:
    path = _file(tmp_path, codecs.BOM_UTF8 + "a\u2029b".encode())
    normalize_file(path, "crlf", breaks="unicode")
    assert path.read_bytes() == codecs.BOM_UTF8 + b"a\r\nb"


def test_binary_files_are_reported_and_skipped(tmp_path: Path) -> None:
    data = b"\x89PNG\r\n\x1a\n\x00\x00\r\n"
    path = _file(tmp_path, data)
    assert scan_file(path).binary
    assert not normalize_file(path, "crlf").changed
    assert path.read_bytes() == data


def test_dry_run_reports_and_writes_nothing(tmp_path: Path) -> None:
    path = _file(tmp_path, b"a\r\n")
    assert normalize_file(path, dry_run=True).changed
    assert path.read_bytes() == b"a\r\n"
    assert not normalize_file(path, "crlf", dry_run=True).changed


def test_keep_lone_cr_reaches_files(tmp_path: Path) -> None:
    path = _file(tmp_path, b"a\rb\r\n")
    normalize_file(path, keep_lone_cr=True)
    assert path.read_bytes() == b"a\rb\n"


def test_bad_arguments_fail_before_reading(tmp_path: Path) -> None:
    missing = tmp_path / "missing.txt"
    with pytest.raises(ValueError, match="style"):
        normalize_file(missing, "lfcr")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="boundary set"):
        scan_file(missing, breaks="all")  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        normalize_file(missing, keep_lone_cr=None)  # type: ignore[arg-type]
    with pytest.raises(FileNotFoundError):
        scan_file(missing)
