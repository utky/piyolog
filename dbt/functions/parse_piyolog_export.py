"""BigQuery Python UDF body for parsing ぴよログ monthly export text.

Self-contained (stdlib only): this file is deployed verbatim as the UDF body
by dbt, so it cannot import the ``piyolog`` package. It is also imported
directly by tests (see ``pyproject.toml`` ``pythonpath``) to unit test the
pure parsing logic without BigQuery.
"""

import re
from dataclasses import asdict, dataclass
from datetime import date, datetime

_SECTION_DELIMITER = "----------"
_DATE_LINE = re.compile(r"^(\d{4})/(\d{1,2})/(\d{1,2})\(.+?\)$")
_AGE_LINE = re.compile(r"^\S+\s*\((?P<age>.+)\)$")
# Separator after HH:MM is usually 3 half-width spaces, rarely 1; detail is optional.
_EVENT_START = re.compile(r"^(\d{1,2}):(\d{2})\s+(\S+)(?:\s+(.*))?$")
_EVENTS_END_MARKER = "母乳合計"
_SUMMARY_END_MARKER = "うんち合計"


@dataclass(frozen=True)
class DailyHeader:
    daily_header_id: str
    child_name: str
    source_year_month: date
    log_date: date
    child_age_raw: str | None


@dataclass(frozen=True)
class Event:
    daily_header_id: str
    event_seq: int
    event_at: datetime
    event_type_raw: str
    detail_raw: str | None


@dataclass(frozen=True)
class DailyNote:
    daily_header_id: str
    note_raw: str


@dataclass(frozen=True)
class ParsedExport:
    headers: list[DailyHeader]
    events: list[Event]
    notes: list[DailyNote]


def _split_sections(raw_content: str) -> list[list[str]]:
    """Split into per-day line groups, one per `----------` delimited section."""
    sections: list[list[str]] = []
    current: list[str] | None = None
    for line in raw_content.splitlines():
        if line.strip() == _SECTION_DELIMITER:
            current = []
            sections.append(current)
        elif current is not None:
            current.append(line)
    return sections


def _parse_date_line(line: str) -> date | None:
    match = _DATE_LINE.match(line.strip())
    if match is None:
        return None
    year, month, day = (int(g) for g in match.groups())
    return date(year, month, day)


def _parse_age_line(line: str) -> str | None:
    match = _AGE_LINE.match(line.strip())
    return match.group("age") if match else None


def _parse_section(
    section_lines: list[str], child_name: str, source_year_month: date
) -> tuple[DailyHeader | None, list[Event], DailyNote | None]:
    state = "HEADER"
    log_date: date | None = None
    child_age_raw: str | None = None
    event_builders: list[dict] = []
    notes_lines: list[str] = []

    for line in section_lines:
        if state == "HEADER":
            if log_date is None:
                found = _parse_date_line(line)
                if found is not None:
                    log_date = found
                continue
            if not line.strip():
                continue
            age = _parse_age_line(line)
            if age is not None:
                child_age_raw = age
                state = "EVENTS"
            continue

        if state == "EVENTS":
            if line.strip().startswith(_EVENTS_END_MARKER):
                state = "SUMMARY"
                continue
            match = _EVENT_START.match(line)
            if match:
                hour, minute, event_type, detail_head = match.groups()
                event_builders.append(
                    {
                        "hour": int(hour),
                        "minute": int(minute),
                        "event_type_raw": event_type,
                        "detail_lines": [detail_head] if detail_head else [],
                    }
                )
                continue
            if line.strip() and event_builders:
                event_builders[-1]["detail_lines"].append(line)
            continue

        if state == "SUMMARY":
            if line.strip().startswith(_SUMMARY_END_MARKER):
                state = "NOTES"
            continue

        if state == "NOTES":
            notes_lines.append(line)

    if log_date is None:
        return None, [], None

    daily_header_id = f"{child_name}:{log_date.isoformat()}"
    header = DailyHeader(
        daily_header_id=daily_header_id,
        child_name=child_name,
        source_year_month=source_year_month,
        log_date=log_date,
        child_age_raw=child_age_raw,
    )
    events = [
        Event(
            daily_header_id=daily_header_id,
            event_seq=seq,
            event_at=datetime(
                log_date.year, log_date.month, log_date.day, builder["hour"], builder["minute"]
            ),
            event_type_raw=builder["event_type_raw"],
            detail_raw="\n".join(builder["detail_lines"]).strip() or None,
        )
        for seq, builder in enumerate(event_builders)
    ]
    note_text = "\n".join(notes_lines).strip()
    note = DailyNote(daily_header_id=daily_header_id, note_raw=note_text) if note_text else None

    return header, events, note


def parse_export_content(
    raw_content: str, child_name: str, source_year_month: date
) -> ParsedExport:
    headers: list[DailyHeader] = []
    events: list[Event] = []
    notes: list[DailyNote] = []

    for section_lines in _split_sections(raw_content):
        header, section_events, note = _parse_section(section_lines, child_name, source_year_month)
        if header is None:
            continue
        headers.append(header)
        events.extend(section_events)
        if note is not None:
            notes.append(note)

    return ParsedExport(headers=headers, events=events, notes=notes)


def parse_piyolog_export(raw_content: str, child_name: str, source_year_month: date) -> dict:
    """BigQuery Python UDF entry point. Returns a dict matching the declared STRUCT."""
    return asdict(parse_export_content(raw_content, child_name, source_year_month))
