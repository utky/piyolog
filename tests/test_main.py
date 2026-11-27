"""Tests for main.py orchestration. Drive and BigQuery are mocked (pytest-mock)."""

import json
from datetime import date, datetime, timezone
from typing import Any

import pytest
from pytest_mock import MockerFixture

from piyolog import main as main_mod
from piyolog.drive import DriveFile

JAN = date(2026, 1, 1)
FEB = date(2026, 2, 1)
T1 = datetime(2026, 7, 1, tzinfo=timezone.utc)
T2 = datetime(2026, 7, 2, tzinfo=timezone.utc)


@pytest.fixture
def env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BQ_PROJECT_ID", "test-project")
    monkeypatch.setenv("DRIVE_CHILD_FOLDERS", json.dumps({"child_a": "folder_a"}))


def _patch_io(
    mocker: MockerFixture, files: list[DriveFile], loaded_at: dict[date, datetime]
) -> Any:
    mocker.patch.object(main_mod.google.auth, "default", return_value=(object(), None))
    mocker.patch.object(main_mod.bigquery, "Client")
    mocker.patch.object(main_mod.drive, "build_drive_service")
    mocker.patch.object(main_mod.drive, "list_piyolog_files", return_value=files)
    mocker.patch.object(
        main_mod.drive, "download_file_content", side_effect=lambda _svc, fid: f"content:{fid}"
    )
    mocker.patch.object(main_mod.bq, "verify_table_exists")
    mocker.patch.object(main_mod.bq, "fetch_loaded_at", return_value=loaded_at)
    return mocker.patch.object(main_mod.bq, "bulk_merge")


def _merged(bulk_merge: Any) -> list[tuple[date, str]]:
    records = bulk_merge.call_args.args[4]
    return [(r.source_year_month, r.drive_file_id) for r in records]


def test_loads_new_and_modified_files_only(env: None, mocker: MockerFixture) -> None:
    files = [
        DriveFile("jan", "【ぴよログ】2026年1月", T1),  # unchanged since last load
        DriveFile("feb", "【ぴよログ】2026年2月", T2),  # new
    ]
    bulk_merge = _patch_io(mocker, files, loaded_at={JAN: T1})

    main_mod.main()

    assert _merged(bulk_merge) == [(FEB, "feb")]


def test_ambiguous_month_is_skipped_others_loaded_then_job_fails(
    env: None, mocker: MockerFixture
) -> None:
    files = [
        DriveFile("jan-1", "【ぴよログ】2026年1月", T1),
        DriveFile("jan-2", "【ぴよログ】2026年1月", T2),
        DriveFile("feb", "【ぴよログ】2026年2月", T2),
    ]
    bulk_merge = _patch_io(mocker, files, loaded_at={})

    with pytest.raises(SystemExit, match="1 month"):
        main_mod.main()

    # the ambiguous month never reaches BigQuery; the other month is still ingested
    assert _merged(bulk_merge) == [(FEB, "feb")]


def test_orphaned_month_is_only_warned(
    env: None, mocker: MockerFixture, caplog: pytest.LogCaptureFixture
) -> None:
    files = [DriveFile("feb", "【ぴよログ】2026年2月", T1)]
    bulk_merge = _patch_io(mocker, files, loaded_at={JAN: T1, FEB: T2})

    main_mod.main()

    assert _merged(bulk_merge) == []
    warnings = [r for r in caplog.records if r.levelname == "WARNING"]
    assert any(getattr(r, "source_year_months", None) == ["2026-01-01"] for r in warnings)
