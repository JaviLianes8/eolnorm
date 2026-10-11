import pytest

from eolnorm import counts, detect, normalize


def test_detect_lf() -> None:
    assert detect("a\nb\nc") == "lf"


def test_detect_crlf() -> None:
    assert detect("a\r\nb\r\n") == "crlf"


def test_detect_cr() -> None:
    assert detect("a\rb\rc") == "cr"


def test_detect_mixed() -> None:
    assert detect("a\nb\r\nc\rd") == "mixed"


def test_detect_none_without_any_ending() -> None:
    assert detect("single line") == "none"


def test_detect_none_on_empty_string() -> None:
    assert detect("") == "none"


def test_normalize_to_lf() -> None:
    assert normalize("a\r\nb\rc\n", to="lf") == "a\nb\nc\n"


def test_normalize_to_crlf() -> None:
    assert normalize("a\nb\rc\r\n", to="crlf") == "a\r\nb\r\nc\r\n"


def test_normalize_to_cr() -> None:
    assert normalize("a\nb\r\nc\r", to="cr") == "a\rb\rc\r"


def test_normalize_defaults_to_lf() -> None:
    assert normalize("a\r\nb") == "a\nb"


def test_normalize_rejects_unknown_style() -> None:
    with pytest.raises(ValueError):
        normalize("a\nb", to="lfcr")  # type: ignore[arg-type]


def test_counts_does_not_double_count_crlf() -> None:
    assert counts("a\r\nb\r\n") == {"lf": 0, "crlf": 2, "cr": 0}


def test_counts_each_kind_separately() -> None:
    assert counts("a\nb\r\nc\rd") == {"lf": 1, "crlf": 1, "cr": 1}


def test_counts_empty_string_is_all_zero() -> None:
    assert counts("") == {"lf": 0, "crlf": 0, "cr": 0}


def test_no_trailing_newline_is_still_counted() -> None:
    assert counts("a\nb") == {"lf": 1, "crlf": 0, "cr": 0}
    assert detect("a\nb") == "lf"
