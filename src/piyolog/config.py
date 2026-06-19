"""Configuration loaded from environment variables."""

import json
import os


class Config:
    def __init__(self) -> None:
        self.bq_project_id: str = _require_env("BQ_PROJECT_ID")
        self.bq_dataset_id: str = os.environ.get("BQ_DATASET_ID", "piyolog_raw")
        self.bq_table_id: str = os.environ.get("BQ_TABLE_ID", "export_files")
        # JSON mapping of child_name -> Drive folder ID
        # e.g. '{"みのり": "folder_id_1", "あきら": "folder_id_2"}'
        self.drive_child_folders: dict[str, str] = _parse_drive_folders(
            _require_env("DRIVE_CHILD_FOLDERS")
        )

    @property
    def bq_table_ref(self) -> str:
        return f"{self.bq_project_id}.{self.bq_dataset_id}.{self.bq_table_id}"


def _require_env(name: str) -> str:
    value = os.environ.get(name)
    if not value:
        raise RuntimeError(f"Required environment variable not set: {name}")
    return value


def _parse_drive_folders(raw: str) -> dict[str, str]:
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as e:
        raise RuntimeError(f"DRIVE_CHILD_FOLDERS is not valid JSON: {e}") from e
    if not isinstance(parsed, dict):
        raise RuntimeError(
            "DRIVE_CHILD_FOLDERS must be a JSON object mapping child_name to folder_id"
        )
    return {str(k): str(v) for k, v in parsed.items()}
