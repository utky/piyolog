"""Tests for the BigQuery Python UDF body (dbt/functions/parse_piyolog_export.py).

Pure function tests, no mocks: the module under test has no BigQuery/network
dependency, only stdlib.

- ``classify_line`` / ``step_section`` / ``step``: table-driven unit tests per transition
- ``parse_export_content`` / ``parse_piyolog_export``: a few end-to-end tests
"""

from dataclasses import replace
from datetime import date, datetime

import pytest
from parse_piyolog_export import (
    AgeLine,
    Blank,
    DailyHeader,
    DailyNote,
    DateLine,
    DaySection,
    Delimiter,
    EndOfFile,
    EventDraft,
    EventsEnd,
    EventStart,
    LineToken,
    ParseState,
    Phase,
    SectionDraft,
    SummaryEnd,
    Text,
    classify_line,
    parse_export_content,
    parse_piyolog_export,
    step,
    step_section,
)

SOURCE_YEAR_MONTH = date(2026, 5, 1)


def _content(*sections: str) -> str:
    """Join daily sections, each prefixed with the `----------` delimiter."""
    return "\n----------\n".join(("", *sections))


def test_single_event_with_detail() -> None:
    content = _content(
        "2026/5/1(金)\n"
        "child_a (4歳4か月20日)\n"
        "\n"
        "07:00   母乳   左20分 ▶ 右20分\n"
        "母乳合計 40分\n"
        "うんち合計 0回\n"
    )
    parsed = parse_export_content(content, "child_a", SOURCE_YEAR_MONTH)

    assert parsed.headers == (
        DailyHeader(
            daily_header_id="child_a:2026-05-01",
            child_name="child_a",
            source_year_month=SOURCE_YEAR_MONTH,
            log_date=date(2026, 5, 1),
            child_age_raw="4歳4か月20日",
        ),
    )
    assert len(parsed.events) == 1
    event = parsed.events[0]
    assert event.daily_header_id == "child_a:2026-05-01"
    assert event.event_seq == 0
    assert event.event_at == datetime(2026, 5, 1, 7, 0)
    assert event.event_type_raw == "母乳"
    assert event.detail_raw == "左20分 ▶ 右20分"
    assert parsed.notes == ()


def test_event_without_detail() -> None:
    content = _content(
        "2026/5/1(金)\n"
        "child_a (4歳4か月20日)\n"
        "\n"
        "07:00   ミルトン交換\n"
        "母乳合計 0分\n"
        "うんち合計 0回\n"
    )
    parsed = parse_export_content(content, "child_a", SOURCE_YEAR_MONTH)

    assert len(parsed.events) == 1
    assert parsed.events[0].event_type_raw == "ミルトン交換"
    assert parsed.events[0].detail_raw is None


def test_event_start_line_single_space_exception() -> None:
    content = _content(
        "2026/5/1(金)\nchild_a (4歳4か月20日)\n\n07:00 おしっこ\n母乳合計 0分\nうんち合計 0回\n"
    )
    parsed = parse_export_content(content, "child_a", SOURCE_YEAR_MONTH)

    assert len(parsed.events) == 1
    assert parsed.events[0].event_type_raw == "おしっこ"


def test_multiline_detail_accumulates_until_next_event() -> None:
    content = _content(
        "2026/5/1(金)\n"
        "child_a (4歳4か月20日)\n"
        "\n"
        "06:30   さんぽ   公園で\n"
        "とても楽しそうだった\n"
        "帰りは眠そうだった\n"
        "07:30   寝る\n"
        "母乳合計 0分\n"
        "うんち合計 0回\n"
    )
    parsed = parse_export_content(content, "child_a", SOURCE_YEAR_MONTH)

    assert len(parsed.events) == 2
    walk = parsed.events[0]
    assert walk.event_type_raw == "さんぽ"
    assert walk.detail_raw == "公園で\nとても楽しそうだった\n帰りは眠そうだった"
    sleep = parsed.events[1]
    assert sleep.event_type_raw == "寝る"
    assert sleep.detail_raw is None


def test_summary_block_is_skipped() -> None:
    content = _content(
        "2026/5/1(金)\n"
        "child_a (4歳4か月20日)\n"
        "\n"
        "07:00   母乳\n"
        "母乳合計 20分\n"
        "ミルク合計 0ml\n"
        "搾母乳合計 0ml\n"
        "睡眠合計 3時間\n"
        "おしっこ合計 5回\n"
        "うんち合計 1回\n"
        "\n"
        "今日は元気でした\n"
    )
    parsed = parse_export_content(content, "child_a", SOURCE_YEAR_MONTH)

    assert len(parsed.events) == 1
    assert parsed.notes == (
        DailyNote(daily_header_id="child_a:2026-05-01", note_raw="今日は元気でした"),
    )


def test_empty_notes_produce_no_row() -> None:
    content = _content(
        "2026/5/1(金)\nchild_a (4歳4か月20日)\n\n07:00   母乳\n母乳合計 0分\nうんち合計 0回\n\n"
    )
    parsed = parse_export_content(content, "child_a", SOURCE_YEAR_MONTH)

    assert parsed.notes == ()


def test_multiple_daily_sections() -> None:
    content = _content(
        "2026/5/1(金)\nchild_a (4歳4か月20日)\n\n07:00   母乳\n母乳合計 0分\nうんち合計 0回\n",
        "2026/5/2(土)\nchild_a (4歳4か月21日)\n\n08:00   おしっこ\n母乳合計 0分\nうんち合計 0回\n",
    )
    parsed = parse_export_content(content, "child_a", SOURCE_YEAR_MONTH)

    assert [h.log_date for h in parsed.headers] == [date(2026, 5, 1), date(2026, 5, 2)]
    assert [e.daily_header_id for e in parsed.events] == [
        "child_a:2026-05-01",
        "child_a:2026-05-02",
    ]


def test_daily_header_id_does_not_collide_across_children() -> None:
    content = _content(
        "2026/5/1(金)\nchild_a (4歳4か月20日)\n\n07:00   母乳\n母乳合計 0分\nうんち合計 0回\n"
    )

    parsed_a = parse_export_content(content, "child_a", SOURCE_YEAR_MONTH)
    parsed_b = parse_export_content(content, "child_b", SOURCE_YEAR_MONTH)

    assert parsed_a.headers[0].daily_header_id == "child_a:2026-05-01"
    assert parsed_b.headers[0].daily_header_id == "child_b:2026-05-01"
    assert parsed_a.headers[0].daily_header_id != parsed_b.headers[0].daily_header_id


def test_event_seq_is_ordinal_within_day() -> None:
    content = _content(
        "2026/5/1(金)\n"
        "child_a (4歳4か月20日)\n"
        "\n"
        "07:00   母乳\n"
        "08:00   おしっこ\n"
        "09:00   うんち\n"
        "母乳合計 0分\n"
        "うんち合計 1回\n"
    )
    parsed = parse_export_content(content, "child_a", SOURCE_YEAR_MONTH)

    assert [e.event_seq for e in parsed.events] == [0, 1, 2]


def test_parse_piyolog_export_returns_struct_compatible_dict() -> None:
    content = _content(
        "2026/5/1(金)\n"
        "child_a (4歳4か月20日)\n"
        "\n"
        "07:00   母乳   左20分\n"
        "母乳合計 20分\n"
        "うんち合計 0回\n"
        "\n"
        "元気です\n"
    )
    result = parse_piyolog_export(content, "child_a", SOURCE_YEAR_MONTH)

    assert set(result.keys()) == {"headers", "events", "notes"}
    # BigQuery ARRAY maps to Python list
    assert all(isinstance(result[k], list) for k in ("headers", "events", "notes"))
    assert result["headers"][0]["daily_header_id"] == "child_a:2026-05-01"
    assert result["events"][0]["event_type_raw"] == "母乳"
    assert result["notes"][0]["note_raw"] == "元気です"


def test_section_without_date_line_is_ignored() -> None:
    content = _content("not a date line\nno events here\n")
    parsed = parse_export_content(content, "child_a", SOURCE_YEAR_MONTH)

    assert parsed.headers == ()
    assert parsed.events == ()
    assert parsed.notes == ()


# --- classify_line -----------------------------------------------------------


@pytest.mark.parametrize(
    ("line", "expected"),
    [
        ("----------", Delimiter()),
        ("  ----------  ", Delimiter()),
        ("", Blank("")),
        ("   ", Blank("   ")),
        ("2026/5/1(金)", DateLine("2026/5/1(金)", date(2026, 5, 1))),
        ("2026/12/31(木)", DateLine("2026/12/31(木)", date(2026, 12, 31))),
        ("child_a (4歳4か月20日)", AgeLine("child_a (4歳4か月20日)", "4歳4か月20日")),
        ("child_a(0か月3日)", AgeLine("child_a(0か月3日)", "0か月3日")),
        (
            "07:00   母乳   左20分 ▶ 右20分",
            EventStart("07:00   母乳   左20分 ▶ 右20分", 7, 0, "母乳", "左20分 ▶ 右20分"),
        ),
        ("7:05 おしっこ", EventStart("7:05 おしっこ", 7, 5, "おしっこ", None)),
        ("23:59   寝る   ", EventStart("23:59   寝る   ", 23, 59, "寝る", None)),
        ("母乳合計 40分", EventsEnd("母乳合計 40分")),
        ("母乳合計   左 20分 / 右 20分", EventsEnd("母乳合計   左 20分 / 右 20分")),
        ("うんち合計 1回", SummaryEnd("うんち合計 1回")),
        ("ミルク合計 0ml", Text("ミルク合計 0ml")),
        ("今日は元気でした", Text("今日は元気でした")),
        ("07:00", Text("07:00")),
    ],
)
def test_classify_line(line: str, expected: LineToken) -> None:
    assert classify_line(line) == expected


# --- step_section ------------------------------------------------------------


def replace_events(section: SectionDraft, events: tuple[EventDraft, ...]) -> SectionDraft:
    return replace(section, events=events)


def with_phase(section: SectionDraft, phase: Phase) -> SectionDraft:
    return replace(section, phase=phase)


_DATE = date(2026, 5, 1)
_DATED = SectionDraft(log_date=_DATE)
_IN_EVENTS = SectionDraft(phase=Phase.EVENTS, log_date=_DATE, child_age_raw="4歳")
_WALK = EventDraft(6, 30, "さんぽ", ("公園で",))


@pytest.mark.parametrize(
    ("section", "token", "expected"),
    [
        # HEADER: wait for the date line, ignoring anything before it
        (SectionDraft(), Text("x"), SectionDraft()),
        (SectionDraft(), AgeLine("a (1歳)", "1歳"), SectionDraft()),
        (SectionDraft(), DateLine("2026/5/1(金)", _DATE), _DATED),
        # HEADER (dated): blanks/others are skipped, the age line moves to EVENTS
        (_DATED, Blank(""), _DATED),
        (_DATED, DateLine("2026/5/2(土)", date(2026, 5, 2)), _DATED),
        (
            _DATED,
            AgeLine("child_a (4歳)", "4歳"),
            SectionDraft(phase=Phase.EVENTS, log_date=_DATE, child_age_raw="4歳"),
        ),
        # EVENTS: event start appends a draft
        (
            _IN_EVENTS,
            EventStart("07:00   母乳   左20分", 7, 0, "母乳", "左20分"),
            replace_events(_IN_EVENTS, (EventDraft(7, 0, "母乳", ("左20分",)),)),
        ),
        (
            _IN_EVENTS,
            EventStart("07:00   寝る", 7, 0, "寝る", None),
            replace_events(_IN_EVENTS, (EventDraft(7, 0, "寝る", ()),)),
        ),
        # EVENTS: non-blank continuation lines are appended verbatim to the last event
        (
            replace_events(_IN_EVENTS, (_WALK,)),
            Text("楽しそうだった"),
            replace_events(
                _IN_EVENTS, (EventDraft(6, 30, "さんぽ", ("公園で", "楽しそうだった")),)
            ),
        ),
        (
            replace_events(_IN_EVENTS, (_WALK,)),
            AgeLine("名前 (メモ)", "メモ"),
            replace_events(_IN_EVENTS, (EventDraft(6, 30, "さんぽ", ("公園で", "名前 (メモ)")),)),
        ),
        (replace_events(_IN_EVENTS, (_WALK,)), Blank(""), replace_events(_IN_EVENTS, (_WALK,))),
        # EVENTS: continuation before any event is dropped
        (_IN_EVENTS, Text("orphan"), _IN_EVENTS),
        # EVENTS -> SUMMARY
        (_IN_EVENTS, EventsEnd("母乳合計 0分"), with_phase(_IN_EVENTS, Phase.SUMMARY)),
        # SUMMARY: everything is skipped until うんち合計
        (
            with_phase(_IN_EVENTS, Phase.SUMMARY),
            Text("ミルク合計 0ml"),
            with_phase(_IN_EVENTS, Phase.SUMMARY),
        ),
        (
            with_phase(_IN_EVENTS, Phase.SUMMARY),
            EventStart("07:00 x", 7, 0, "x", None),
            with_phase(_IN_EVENTS, Phase.SUMMARY),
        ),
        (
            with_phase(_IN_EVENTS, Phase.SUMMARY),
            SummaryEnd("うんち合計 1回"),
            with_phase(_IN_EVENTS, Phase.NOTES),
        ),
        # NOTES: every line is kept verbatim, whatever it looks like
        (
            with_phase(_IN_EVENTS, Phase.NOTES),
            Blank(""),
            SectionDraft(phase=Phase.NOTES, log_date=_DATE, child_age_raw="4歳", note_lines=("",)),
        ),
        (
            with_phase(_IN_EVENTS, Phase.NOTES),
            EventStart("07:00 散歩した", 7, 0, "散歩した", None),
            SectionDraft(
                phase=Phase.NOTES,
                log_date=_DATE,
                child_age_raw="4歳",
                note_lines=("07:00 散歩した",),
            ),
        ),
    ],
)
def test_step_section(section: SectionDraft, token: LineToken, expected: SectionDraft) -> None:
    assert step_section(section, token) == expected


# --- step (file-level reducer) -----------------------------------------------

_NOTES_DONE = SectionDraft(
    phase=Phase.NOTES, log_date=_DATE, child_age_raw="4歳", note_lines=("", "メモ", "")
)
_FINAL = DaySection(log_date=_DATE, child_age_raw="4歳", events=(), note_raw="メモ")


@pytest.mark.parametrize(
    ("state", "token", "expected"),
    [
        # lines before the first delimiter are ignored
        (ParseState(), Text("ぴよログ 2026年5月"), ParseState()),
        (ParseState(), DateLine("2026/5/1(金)", _DATE), ParseState()),
        # delimiter opens a section
        (ParseState(), Delimiter(), ParseState(current=SectionDraft())),
        # delimiter / EOF finalize the current section
        (ParseState(current=_NOTES_DONE), Delimiter(), ParseState(SectionDraft(), (_FINAL,))),
        (ParseState(current=_NOTES_DONE), EndOfFile(), ParseState(None, (_FINAL,))),
        # sections without a date are dropped on finalize
        (ParseState(current=SectionDraft()), EndOfFile(), ParseState()),
        # a section that never reached NOTES is still finalized (no note)
        (
            ParseState(current=_IN_EVENTS),
            EndOfFile(),
            ParseState(None, (DaySection(_DATE, "4歳", (), None),)),
        ),
        # other tokens are delegated to step_section
        (
            ParseState(current=SectionDraft()),
            DateLine("2026/5/1(金)", _DATE),
            ParseState(current=_DATED),
        ),
    ],
)
def test_step(state: ParseState, token: LineToken, expected: ParseState) -> None:
    assert step(state, token) == expected
