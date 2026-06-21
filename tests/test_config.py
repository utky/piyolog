"""Tests for config.py."""

import json

import pytest

from piyolog.config import _parse_drive_folders, _require_env


def test_parse_drive_folders_valid() -> None:
    raw = json.dumps({"child_a": "folder_id_1", "child_b": "folder_id_2"})
    result = _parse_drive_folders(raw)
    assert result == {"child_a": "folder_id_1", "child_b": "folder_id_2"}


def test_parse_drive_folders_single_child() -> None:
    raw = json.dumps({"child_a": "abc123"})
    assert _parse_drive_folders(raw) == {"child_a": "abc123"}


def test_parse_drive_folders_invalid_json() -> None:
    with pytest.raises(RuntimeError, match="not valid JSON"):
        _parse_drive_folders("{not: json}")


def test_parse_drive_folders_not_object() -> None:
    with pytest.raises(RuntimeError, match="must be a JSON object"):
        _parse_drive_folders(json.dumps(["a", "b"]))


def test_require_env_present(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MY_TEST_VAR", "hello")
    assert _require_env("MY_TEST_VAR") == "hello"


def test_require_env_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MY_TEST_VAR", raising=False)
    with pytest.raises(RuntimeError, match="MY_TEST_VAR"):
        _require_env("MY_TEST_VAR")


def test_config_bq_table_ref(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("BQ_PROJECT_ID", "my-project")
    monkeypatch.setenv("BQ_DATASET_ID", "my_dataset")
    monkeypatch.setenv("BQ_TABLE_ID", "my_table")
    monkeypatch.setenv("DRIVE_CHILD_FOLDERS", json.dumps({"child": "folder_id"}))

    from piyolog.config import Config
    cfg = Config()
    assert cfg.bq_table_ref == "my-project.my_dataset.my_table"
