"""is_binary follows git's convert.c statistics (the lone CR rule aside)."""

from __future__ import annotations

import pytest

from eolnorm import is_binary


def test_plain_text_is_not_binary() -> None:
    assert not is_binary(b"hello\r\nworld\n")
    assert not is_binary(b"")
    assert not is_binary("caf\u00e9 \u2603\n".encode())


def test_a_nul_byte_anywhere_is_binary() -> None:
    assert is_binary(b"\x00")
    assert is_binary(b"a" * 100_000 + b"\x00")


def test_one_control_byte_per_128_printable_is_the_limit() -> None:
    assert is_binary(b"a" * 127 + b"\x01")
    assert not is_binary(b"a" * 128 + b"\x01")
    assert is_binary(b"a" * 255 + b"\x01\x02")
    assert not is_binary(b"a" * 256 + b"\x01\x02")


def test_cr_and_lf_count_for_nothing() -> None:
    assert is_binary(b"a" * 127 + b"\r\n" * 50 + b"\x01")


def test_bs_ht_esc_and_ff_are_printable() -> None:
    assert not is_binary(b"\b\t\x1b\x0c" * 32)
    assert not is_binary(b"\b" * 127 + b"\x01" + b"a")


def test_del_and_other_controls_are_not_printable() -> None:
    for byte in [*range(1, 8), 0x0B, *range(0x0E, 0x1B), *range(0x1C, 0x20), 0x7F]:
        assert is_binary(b"a" * 64 + bytes([byte]) + b"a" * 63), byte


def test_high_bytes_are_printable() -> None:
    assert not is_binary(bytes(range(0x80, 0x100)) + b"\x01")


def test_a_final_ctrl_z_is_forgiven() -> None:
    assert not is_binary(b"a" * 10 + b"\x1a")
    assert is_binary(b"\x1a" + b"a" * 10)
    assert is_binary(b"a" * 10 + b"\x1a\x1a")


def test_a_lone_cr_alone_does_not_make_binary() -> None:
    assert not is_binary(b"old\rmac\rfile\r")


def test_only_bytes_are_accepted() -> None:
    for bad in ("text", bytearray(b"a"), memoryview(b"a"), None):
        with pytest.raises(TypeError):
            is_binary(bad)  # type: ignore[arg-type]
