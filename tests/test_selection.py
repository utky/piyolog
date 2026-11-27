"""Tests for selection.py (pure functions, no mocks)."""

from datetime import date, datetime, timezone

import pytest

from piyolog.drive import DriveFile
from piyolog.selection import (
    AmbiguousMonth,
    FileSelection,
    MonthlyFile,
    find_orphaned_months,
    needs_reload,
    select_monthly_files,
)


def _at(day: int) -> datetime:
    return datetime(2026, 7, day, tzinfo=timezone.utc)


def _file(file_id: str, name: str, day: int = 1) -> DriveFile:
    return DriveFile(file_id=file_id, name=name, modified_at=_at(day))


JAN = date(2026, 1, 1)
FEB = date(2026, 2, 1)


def test_one_file_per_month_is_selected() -> None:
    jan = _file("f1", "【ぴよログ】2026年1月.txt")
    feb = _file("f2", "【ぴよログ】2026年2月")

    result = select_monthly_files([feb, jan])

    assert result == FileSelection(
        selected=(MonthlyFile(JAN, jan), MonthlyFile(FEB, feb)),
        ambiguous=(),
        unrecognized=(),
    )


def test_multiple_files_for_same_month_are_ambiguous_and_not_selected() -> None:
    newer = _file("f-new", "【ぴよログ】2026年1月", day=5)
    older = _file("f-old", "【ぴよログ】2026年1月", day=2)
    feb = _file("f2", "【ぴよログ】2026年2月")

    result = select_monthly_files([newer, feb, older])

    assert result.selected == (MonthlyFile(FEB, feb),)
    # ordered by modified_at so logs are stable and easy to read
    assert result.ambiguous == (AmbiguousMonth(JAN, (older, newer)),)


def test_name_with_and_without_txt_maps_to_same_month() -> None:
    a = _file("a", "【ぴよログ】2026年1月.txt")
    b = _file("b", "【ぴよログ】2026年1月")

    result = select_monthly_files([a, b])

    assert result.selected == ()
    assert [m.source_year_month for m in result.ambiguous] == [JAN]


def test_unrecognized_names_are_reported_separately() -> None:
    bad = _file("x", "【ぴよログ】メモ.txt")
    jan = _file("f1", "【ぴよログ】2026年1月")

    result = select_monthly_files([bad, jan])

    assert result.unrecognized == (bad,)
    assert result.selected == (MonthlyFile(JAN, jan),)


def test_months_in_drive_includes_ambiguous_months() -> None:
    result = select_monthly_files(
        [
            _file("a", "【ぴよログ】2026年1月"),
            _file("b", "【ぴよログ】2026年1月"),
            _file("c", "【ぴよログ】2026年2月"),
        ]
    )

    assert result.months_in_drive == frozenset({JAN, FEB})


def test_empty_folder() -> None:
    assert select_monthly_files([]) == FileSelection((), (), ())


@pytest.mark.parametrize(
    ("drive_modified_at", "existing_loaded_at", "expected"),
    [
        (_at(1), None, True),  # new month
        (_at(2), _at(1), True),  # modified after last load
        (_at(1), _at(1), False),  # unchanged (boundary)
        (_at(1), _at(2), False),  # loaded after last modification
    ],
)
def test_needs_reload(
    drive_modified_at: datetime, existing_loaded_at: datetime | None, expected: bool
) -> None:
    assert needs_reload(drive_modified_at, existing_loaded_at) is expected


@pytest.mark.parametrize(
    ("raw_months", "drive_months", "expected"),
    [
        ([], [], ()),
        ([JAN, FEB], [JAN, FEB], ()),
        ([JAN, FEB], [FEB], (JAN,)),
        ([FEB, JAN], [], (JAN, FEB)),
        ([], [JAN], ()),  # new months in Drive are not orphans
    ],
)
def test_find_orphaned_months(
    raw_months: list[date], drive_months: list[date], expected: tuple[date, ...]
) -> None:
    assert find_orphaned_months(raw_months, drive_months) == expected
