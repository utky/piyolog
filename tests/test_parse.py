"""Tests for the BigQuery Python UDF body (dbt/functions/parse_piyolog_export.py).

Pure function tests, no mocks: the module under test has no BigQuery/network
dependency, only stdlib.
"""

from datetime import date, datetime

from parse_piyolog_export import DailyHeader, DailyNote, parse_export_content, parse_piyolog_export

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

    assert parsed.headers == [
        DailyHeader(
            daily_header_id="child_a:2026-05-01",
            child_name="child_a",
            source_year_month=SOURCE_YEAR_MONTH,
            log_date=date(2026, 5, 1),
            child_age_raw="4歳4か月20日",
        )
    ]
    assert len(parsed.events) == 1
    event = parsed.events[0]
    assert event.daily_header_id == "child_a:2026-05-01"
    assert event.event_seq == 0
    assert event.event_at == datetime(2026, 5, 1, 7, 0)
    assert event.event_type_raw == "母乳"
    assert event.detail_raw == "左20分 ▶ 右20分"
    assert parsed.notes == []


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
    assert parsed.notes == [
        DailyNote(daily_header_id="child_a:2026-05-01", note_raw="今日は元気でした")
    ]


def test_empty_notes_produce_no_row() -> None:
    content = _content(
        "2026/5/1(金)\nchild_a (4歳4か月20日)\n\n07:00   母乳\n母乳合計 0分\nうんち合計 0回\n\n"
    )
    parsed = parse_export_content(content, "child_a", SOURCE_YEAR_MONTH)

    assert parsed.notes == []


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


def test_parse_piyolog_export_returns_json_serializable_dict() -> None:
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
    assert result["headers"][0]["daily_header_id"] == "child_a:2026-05-01"
    assert result["events"][0]["event_type_raw"] == "母乳"
    assert result["notes"][0]["note_raw"] == "元気です"


def test_section_without_date_line_is_ignored() -> None:
    content = _content("not a date line\nno events here\n")
    parsed = parse_export_content(content, "child_a", SOURCE_YEAR_MONTH)

    assert parsed.headers == []
    assert parsed.events == []
    assert parsed.notes == []
