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


def test_counts_keys_follow_the_boundary_set() -> None:
    assert list(counts("")) == ["lf", "crlf", "cr"]
    assert list(counts("", breaks="unicode")) == ["lf", "crlf", "cr", "vt", "ff", "nel", "ls", "ps"]
    assert list(counts("", breaks="splitlines")) == [
        *["lf", "crlf", "cr", "vt", "ff", "fs", "gs", "rs", "nel", "ls", "ps"]
    ]


def test_ascii_set_ignores_the_unicode_breaks() -> None:
    text = "a\x0bb\x0cc\x85d\u2028e\u2029f\x1cg"
    assert detect(text) == "none"
    assert normalize(text, "crlf") == text


def test_unicode_set_counts_each_mandatory_break() -> None:
    text = "a\x0bb\x0cc\x85d\u2028e\u2029f\r\ng\x1ch"
    tally = counts(text, breaks="unicode")
    assert tally == {"lf": 0, "crlf": 1, "cr": 0, "vt": 1, "ff": 1, "nel": 1, "ls": 1, "ps": 1}


def test_splitlines_set_adds_the_information_separators() -> None:
    tally = counts("a\x1cb\x1dc\x1ed", breaks="splitlines")
    assert (tally["fs"], tally["gs"], tally["rs"]) == (1, 1, 1)
    assert sum(tally.values()) == 3


def test_detect_names_a_single_unicode_kind() -> None:
    assert detect("a\x85b\x85", breaks="unicode") == "nel"
    assert detect("a\u2029b", breaks="unicode") == "ps"
    assert detect("a\x85b\n", breaks="unicode") == "mixed"


def test_normalize_converts_unicode_breaks() -> None:
    assert normalize("a\x85b\u2028c\r\nd", "lf", breaks="unicode") == "a\nb\nc\nd"
    assert normalize("a\x1eb", "crlf", breaks="splitlines") == "a\r\nb"
    assert normalize("a\x1eb", "crlf", breaks="unicode") == "a\x1eb"


def test_bytes_in_bytes_out() -> None:
    data = b"caf\xe9\r\nna\xefve\rx\n"
    assert normalize(data) == b"caf\xe9\nna\xefve\nx\n"
    assert normalize(data, "crlf") == b"caf\xe9\r\nna\xefve\r\nx\r\n"
    assert counts(data) == {"lf": 1, "crlf": 1, "cr": 1}
    assert detect(b"a\r\nb\r\n") == "crlf"


def test_bytes_refuse_the_unicode_sets() -> None:
    with pytest.raises(ValueError, match="decoded text"):
        counts(b"a\x85b", breaks="unicode")
    with pytest.raises(ValueError, match="decoded text"):
        normalize(b"a\nb", breaks="splitlines")


def test_other_types_are_rejected() -> None:
    for bad in (bytearray(b"a\n"), memoryview(b"a\n"), 5, None, ["a\n"]):
        with pytest.raises(TypeError, match="expected str or bytes"):
            counts(bad)  # type: ignore[arg-type]
        with pytest.raises(TypeError, match="expected str or bytes"):
            normalize(bad)  # type: ignore[type-var]


def test_unknown_boundary_set_is_rejected() -> None:
    with pytest.raises(ValueError, match="boundary set"):
        detect("a", breaks="all")  # type: ignore[arg-type]
    with pytest.raises(ValueError, match="boundary set"):
        normalize("a", breaks=None)  # type: ignore[arg-type]


def test_keep_lone_cr_converts_only_real_endings() -> None:
    assert normalize("a\rb\r\nc\n", "lf", keep_lone_cr=True) == "a\rb\nc\n"
    assert normalize("a\rb\r\nc\n", "crlf", keep_lone_cr=True) == "a\rb\r\nc\r\n"
    assert normalize("a\r\r\nb", "lf", keep_lone_cr=True) == "a\r\nb"
    assert normalize(b"a\rb\n", "cr", keep_lone_cr=True) == b"a\rb\r"


def test_keep_lone_cr_must_be_a_bool() -> None:
    with pytest.raises(TypeError):
        normalize("a", keep_lone_cr=1)  # type: ignore[arg-type]


def test_normalize_is_idempotent_and_reversible_on_clean_text() -> None:
    text = "one\r\ntwo\rthree\nfour"
    for style in ("lf", "crlf", "cr"):
        once = normalize(text, style)
        assert normalize(once, style) == once
        assert normalize(once, "lf") == "one\ntwo\nthree\nfour"
