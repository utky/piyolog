"""BigQuery Python UDF body for parsing ぴよログ monthly export text.

Self-contained (stdlib only): this file is deployed verbatim as the UDF body
by dbt, so it cannot import the ``piyolog`` package. It is also imported
directly by tests (see ``pyproject.toml`` ``pythonpath``) to unit test the
pure parsing logic without BigQuery.

BigQuery runs Python UDFs on ``python-3.11`` only, so this file must not use
syntax newer than 3.11 (e.g. ``type`` statements, PEP 695 generics).

Structure (reducer + fold, see ADR-0009):

1. ``classify_line``: line -> ``LineToken`` (context-free)
2. ``step``: ``(ParseState, LineToken) -> ParseState`` (pure state transition)
3. ``parse_export_content``: ``functools.reduce(step, tokenize(...), ParseState())``
   followed by conversion of completed sections into output rows
"""

import re
from dataclasses import asdict, dataclass, replace
from datetime import date, datetime
from enum import Enum
from functools import reduce
from typing import Iterator, Union

_SECTION_DELIMITER = "----------"
_DATE_LINE = re.compile(r"^(\d{4})/(\d{1,2})/(\d{1,2})\(.+?\)$")
_AGE_LINE = re.compile(r"^\S+\s*\((?P<age>.+)\)$")
# Separator after HH:MM is usually 3 half-width spaces, rarely 1; detail is optional.
_EVENT_START = re.compile(r"^(\d{1,2}):(\d{2})\s+(\S+)(?:\s+(.*))?$")
_EVENTS_END_MARKER = "母乳合計"
_SUMMARY_END_MARKER = "うんち合計"


# --- Line tokens -------------------------------------------------------------
# Every token except Delimiter/EndOfFile keeps the original line, because the
# meaning of a line depends on the parser phase (e.g. in NOTES everything is text).


@dataclass(frozen=True)
class Delimiter:
    """`----------` line: starts a new daily section."""


@dataclass(frozen=True)
class EndOfFile:
    """Sentinel appended by ``tokenize`` so the last section is finalized by ``step``."""


@dataclass(frozen=True)
class DateLine:
    line: str
    log_date: date


@dataclass(frozen=True)
class AgeLine:
    line: str
    child_age_raw: str


@dataclass(frozen=True)
class EventStart:
    line: str
    hour: int
    minute: int
    event_type_raw: str
    detail_head: str | None


@dataclass(frozen=True)
class EventsEnd:
    """`母乳合計 ...` line: end of EVENTS, start of SUMMARY."""

    line: str


@dataclass(frozen=True)
class SummaryEnd:
    """`うんち合計 ...` line: end of SUMMARY, start of NOTES."""

    line: str


@dataclass(frozen=True)
class Blank:
    line: str


@dataclass(frozen=True)
class Text:
    line: str


LineToken = Union[
    Delimiter, EndOfFile, DateLine, AgeLine, EventStart, EventsEnd, SummaryEnd, Blank, Text
]


def classify_line(line: str) -> LineToken:
    """Classify a single line without any parser context."""
    stripped = line.strip()
    if stripped == _SECTION_DELIMITER:
        return Delimiter()
    if not stripped:
        return Blank(line)
    if stripped.startswith(_EVENTS_END_MARKER):
        return EventsEnd(line)
    if stripped.startswith(_SUMMARY_END_MARKER):
        return SummaryEnd(line)
    event = _EVENT_START.match(line)
    if event is not None:
        hour, minute, event_type, detail_head = event.groups()
        return EventStart(line, int(hour), int(minute), event_type, detail_head or None)
    date_match = _DATE_LINE.match(stripped)
    if date_match is not None:
        year, month, day = (int(g) for g in date_match.groups())
        return DateLine(line, date(year, month, day))
    age = _AGE_LINE.match(stripped)
    if age is not None:
        return AgeLine(line, age.group("age"))
    return Text(line)


def tokenize(raw_content: str) -> Iterator[LineToken]:
    for line in raw_content.splitlines():
        yield classify_line(line)
    yield EndOfFile()


# --- Parser state ------------------------------------------------------------


class Phase(Enum):
    HEADER = "HEADER"
    EVENTS = "EVENTS"
    SUMMARY = "SUMMARY"
    NOTES = "NOTES"


@dataclass(frozen=True)
class EventDraft:
    hour: int
    minute: int
    event_type_raw: str
    detail_lines: tuple[str, ...] = ()


@dataclass(frozen=True)
class SectionDraft:
    """A daily section being parsed."""

    phase: Phase = Phase.HEADER
    log_date: date | None = None
    child_age_raw: str | None = None
    events: tuple[EventDraft, ...] = ()
    note_lines: tuple[str, ...] = ()


@dataclass(frozen=True)
class DaySection:
    """A finalized daily section (has a date), independent of child/month."""

    log_date: date
    child_age_raw: str | None
    events: tuple[EventDraft, ...]
    note_raw: str | None


@dataclass(frozen=True)
class ParseState:
    # None until the first delimiter: lines before it (file header) are ignored.
    current: SectionDraft | None = None
    completed: tuple[DaySection, ...] = ()


def finalize_section(section: SectionDraft | None) -> tuple[DaySection, ...]:
    """Turn a draft into 0 or 1 finalized sections. Sections without a date are dropped."""
    if section is None or section.log_date is None:
        return ()
    note_raw = "\n".join(section.note_lines).strip() or None
    return (DaySection(section.log_date, section.child_age_raw, section.events, note_raw),)


def step_section(section: SectionDraft, token: LineToken) -> SectionDraft:
    """State transition within a daily section (delimiters/EOF are handled by ``step``)."""
    if section.phase is Phase.HEADER:
        if section.log_date is None:
            if isinstance(token, DateLine):
                return replace(section, log_date=token.log_date)
            return section
        if isinstance(token, AgeLine):
            return replace(section, child_age_raw=token.child_age_raw, phase=Phase.EVENTS)
        return section

    if section.phase is Phase.EVENTS:
        if isinstance(token, EventsEnd):
            return replace(section, phase=Phase.SUMMARY)
        if isinstance(token, EventStart):
            head = (token.detail_head,) if token.detail_head else ()
            draft = EventDraft(token.hour, token.minute, token.event_type_raw, head)
            return replace(section, events=section.events + (draft,))
        if isinstance(token, Blank) or not section.events:
            return section
        # Any other non-blank line continues the detail of the previous event.
        last = section.events[-1]
        appended = replace(last, detail_lines=last.detail_lines + (token.line,))
        return replace(section, events=section.events[:-1] + (appended,))

    if section.phase is Phase.SUMMARY:
        if isinstance(token, SummaryEnd):
            return replace(section, phase=Phase.NOTES)
        return section

    # Phase.NOTES: keep every line verbatim (including blanks and event-like lines).
    return replace(section, note_lines=section.note_lines + (token.line,))


def step(state: ParseState, token: LineToken) -> ParseState:
    """Reducer over the whole file."""
    if isinstance(token, Delimiter):
        return ParseState(SectionDraft(), state.completed + finalize_section(state.current))
    if isinstance(token, EndOfFile):
        return ParseState(None, state.completed + finalize_section(state.current))
    if state.current is None:
        return state
    return replace(state, current=step_section(state.current, token))


def parse_sections(raw_content: str) -> tuple[DaySection, ...]:
    return reduce(step, tokenize(raw_content), ParseState()).completed


# --- Output rows -------------------------------------------------------------


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
    headers: tuple[DailyHeader, ...]
    events: tuple[Event, ...]
    notes: tuple[DailyNote, ...]


def daily_header_id(child_name: str, log_date: date) -> str:
    return f"{child_name}:{log_date.isoformat()}"


def to_rows(
    section: DaySection, child_name: str, source_year_month: date
) -> tuple[DailyHeader, tuple[Event, ...], tuple[DailyNote, ...]]:
    header_id = daily_header_id(child_name, section.log_date)
    header = DailyHeader(
        daily_header_id=header_id,
        child_name=child_name,
        source_year_month=source_year_month,
        log_date=section.log_date,
        child_age_raw=section.child_age_raw,
    )
    d = section.log_date
    events = tuple(
        Event(
            daily_header_id=header_id,
            event_seq=seq,
            event_at=datetime(d.year, d.month, d.day, draft.hour, draft.minute),
            event_type_raw=draft.event_type_raw,
            detail_raw="\n".join(draft.detail_lines).strip() or None,
        )
        for seq, draft in enumerate(section.events)
    )
    notes = (DailyNote(header_id, section.note_raw),) if section.note_raw else ()
    return header, events, notes


def parse_export_content(
    raw_content: str, child_name: str, source_year_month: date
) -> ParsedExport:
    rows = [to_rows(s, child_name, source_year_month) for s in parse_sections(raw_content)]
    return ParsedExport(
        headers=tuple(header for header, _, _ in rows),
        events=tuple(event for _, events, _ in rows for event in events),
        notes=tuple(note for _, _, notes in rows for note in notes),
    )


def parse_piyolog_export(raw_content: str, child_name: str, source_year_month: date) -> dict:
    """BigQuery Python UDF entry point. Returns a dict matching the declared STRUCT."""
    parsed = parse_export_content(raw_content, child_name, source_year_month)
    return {
        "headers": [asdict(h) for h in parsed.headers],
        "events": [asdict(e) for e in parsed.events],
        "notes": [asdict(n) for n in parsed.notes],
    }
