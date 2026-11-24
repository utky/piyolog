"""Tests for drive.py pure functions."""

from datetime import date

import pytest

from piyolog.drive import PIYOLOG_FILENAME_PATTERN, parse_year_month_from_filename


@pytest.mark.parametrize(
    "file_name, expected",
    [
        ("【ぴよログ】2024年10月.txt", date(2024, 10, 1)),
        ("【ぴよログ】2021年12月.txt", date(2021, 12, 1)),
        ("【ぴよログ】2026年1月.txt", date(2026, 1, 1)),
        ("【ぴよログ】2023年9月.txt", date(2023, 9, 1)),
        # without .txt extension
        ("【ぴよログ】2024年10月", date(2024, 10, 1)),
        ("【ぴよログ】2022年3月", date(2022, 3, 1)),
        # leading path component should still work
        ("path/to/【ぴよログ】2022年3月.txt", date(2022, 3, 1)),
        ("path/to/【ぴよログ】2022年3月", date(2022, 3, 1)),
    ],
)
def test_parse_year_month_valid(file_name: str, expected: date) -> None:
    assert parse_year_month_from_filename(file_name) == expected


@pytest.mark.parametrize(
    "file_name",
    [
        "ぴよログ2024年10月.txt",  # missing 【】
        "ぴよログ2024年10月",  # missing 【】, no extension
        "【ぴよログ】2024年10月.csv",  # wrong extension
        "【ぴよログ】2024年.txt",  # missing month
        "【ぴよログ】2024年",  # missing month, no extension
        "notes.txt",
        "",
    ],
)
def test_parse_year_month_invalid(file_name: str) -> None:
    with pytest.raises(ValueError):
        parse_year_month_from_filename(file_name)


def test_filename_pattern_does_not_match_csv() -> None:
    assert not PIYOLOG_FILENAME_PATTERN.search("【ぴよログ】2024年10月.csv")


def test_filename_pattern_matches_single_digit_month() -> None:
    assert PIYOLOG_FILENAME_PATTERN.search("【ぴよログ】2024年1月.txt")
