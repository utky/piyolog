"""Cloud Run job entry point for ぴよログ raw layer ingestion.

Usage:
    uv run python -m piyolog.main

Environment variables:
    BQ_PROJECT_ID           - Google Cloud project ID (required)
    BQ_DATASET_ID           - BigQuery dataset ID (default: piyolog_raw)
    BQ_TABLE_ID             - BigQuery table ID (default: export_files)
    DRIVE_CHILD_FOLDERS     - JSON mapping child_name -> Drive folder ID (required)
                              e.g. '{"child1": "1ABC...", "child2": "1DEF..."}'
    LOG_LEVEL               - Logging level (default: INFO). Set to DEBUG for verbose output.
    GOOGLE_APPLICATION_CREDENTIALS - path to service account JSON (optional if running on GCP)
"""

import json
import logging
import os

import google.auth
from google.cloud import bigquery

from piyolog import bq, drive
from piyolog.config import Config

# Derive the set of standard LogRecord attributes from an actual LogRecord instance
# so that any extra={} fields passed by callers are forwarded to the JSON output.
_STDLIB_LOG_ATTRS = frozenset(logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys())


class _JsonFormatter(logging.Formatter):
    """Emit one JSON object per line for Cloud Logging structured log ingestion."""

    def format(self, record: logging.LogRecord) -> str:
        obj: dict = {
            "severity": record.levelname,
            "message": record.getMessage(),
        }
        extra = {k: v for k, v in record.__dict__.items() if k not in _STDLIB_LOG_ATTRS}
        if extra:
            obj.update(extra)
        if record.exc_info:
            obj["exception"] = self.formatException(record.exc_info)
        return json.dumps(obj, ensure_ascii=False)


def _setup_logging() -> None:
    level = os.environ.get("LOG_LEVEL", "INFO").upper()
    handler = logging.StreamHandler()
    handler.setFormatter(_JsonFormatter())
    logging.basicConfig(level=level, handlers=[handler])


log = logging.getLogger(__name__)


def main() -> None:
    _setup_logging()
    config = Config()
    log.info(
        "Starting ぴよログ raw layer ingestion",
        extra={
            "bq_target": config.bq_table_ref,
            "children": list(config.drive_child_folders.keys()),
        },
    )

    credentials, _ = google.auth.default(scopes=["https://www.googleapis.com/auth/drive.readonly"])
    drive_service = drive.build_drive_service(credentials)
    bq_client = bigquery.Client(project=config.bq_project_id)

    bq.verify_table_exists(
        bq_client, config.bq_project_id, config.bq_dataset_id, config.bq_table_id
    )

    records: list[bq.ExportRecord] = []

    for child_name, folder_id in config.drive_child_folders.items():
        log.info("Listing files", extra={"child_name": child_name, "folder_id": folder_id})
        files = drive.list_piyolog_files(drive_service, folder_id)
        log.info("Found files", extra={"child_name": child_name, "count": len(files)})

        loaded_at_map = bq.fetch_loaded_at(
            bq_client, config.bq_project_id, config.bq_dataset_id, config.bq_table_id, child_name
        )

        for drive_file in files:
            try:
                source_year_month = drive.parse_year_month_from_filename(drive_file.name)
            except ValueError as e:
                log.warning(
                    "Skipping file with unrecognized name",
                    extra={
                        "child_name": child_name,
                        "file_name": drive_file.name,
                        "reason": str(e),
                    },
                )
                continue

            existing_loaded_at = loaded_at_map.get(source_year_month)
            if existing_loaded_at is not None and drive_file.modified_at <= existing_loaded_at:
                log.debug(
                    "Skipping unmodified file",
                    extra={
                        "child_name": child_name,
                        "file_name": drive_file.name,
                        "drive_modified_at": drive_file.modified_at.isoformat(),
                        "existing_loaded_at": existing_loaded_at.isoformat(),
                    },
                )
                continue

            log.info(
                "Downloading file",
                extra={"child_name": child_name, "file_name": drive_file.name},
            )
            content = drive.download_file_content(drive_service, drive_file.file_id)
            records.append(
                bq.ExportRecord(
                    child_name=child_name,
                    source_year_month=source_year_month,
                    file_name=drive_file.name,
                    drive_file_id=drive_file.file_id,
                    raw_content=content,
                    loaded_at=bq.utcnow(),
                )
            )

    bq.bulk_merge(
        bq_client, config.bq_project_id, config.bq_dataset_id, config.bq_table_id, records
    )
    log.info("Done", extra={"processed": len(records)})


if __name__ == "__main__":
    main()
