"""Pure business logic for deciding which Drive files to ingest into the raw layer.

The raw layer is keyed by ``(child_name, source_year_month)`` (one file per child per month).
Drive does not enforce that: a folder can contain several files that map to the same month
(e.g. another child's export misplaced into this folder). Such months are reported as
ambiguous and left untouched instead of guessing which file is correct.
"""

from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import date, datetime

from piyolog.drive import DriveFile, parse_year_month_from_filename


@dataclass(frozen=True)
class MonthlyFile:
    source_year_month: date
    file: DriveFile


@dataclass(frozen=True)
class AmbiguousMonth:
    """A month with more than one candidate file in the same child's folder."""

    source_year_month: date
    files: tuple[DriveFile, ...]


@dataclass(frozen=True)
class FileSelection:
    selected: tuple[MonthlyFile, ...]
    ambiguous: tuple[AmbiguousMonth, ...]
    unrecognized: tuple[DriveFile, ...]

    @property
    def months_in_drive(self) -> frozenset[date]:
        """Every month that has at least one file in Drive (selected or ambiguous)."""
        return frozenset(m.source_year_month for m in self.selected) | frozenset(
            a.source_year_month for a in self.ambiguous
        )


def select_monthly_files(files: Sequence[DriveFile]) -> FileSelection:
    """Group a child's Drive files by month; months with multiple files are ambiguous."""
    by_month: dict[date, list[DriveFile]] = {}
    unrecognized: list[DriveFile] = []
    for f in files:
        try:
            month = parse_year_month_from_filename(f.name)
        except ValueError:
            unrecognized.append(f)
            continue
        by_month.setdefault(month, []).append(f)

    selected: list[MonthlyFile] = []
    ambiguous: list[AmbiguousMonth] = []
    for month in sorted(by_month):
        candidates = by_month[month]
        if len(candidates) == 1:
            selected.append(MonthlyFile(month, candidates[0]))
        else:
            ordered = tuple(sorted(candidates, key=lambda f: (f.modified_at, f.file_id)))
            ambiguous.append(AmbiguousMonth(month, ordered))

    return FileSelection(tuple(selected), tuple(ambiguous), tuple(unrecognized))


def needs_reload(drive_modified_at: datetime, existing_loaded_at: datetime | None) -> bool:
    """A file is (re)loaded if it is new to raw or was modified after the last load."""
    return existing_loaded_at is None or drive_modified_at > existing_loaded_at


def find_orphaned_months(
    raw_months: Iterable[date], drive_months: Iterable[date]
) -> tuple[date, ...]:
    """Months present in raw but no longer in Drive (e.g. the file was deleted or moved)."""
    return tuple(sorted(set(raw_months) - set(drive_months)))
