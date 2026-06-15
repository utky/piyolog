"""Cloud Run job entry point for ぴよログ raw layer ingestion.

Usage:
    uv run python -m piyolog.main

Environment variables:
    BQ_PROJECT_ID           - Google Cloud project ID (required)
    BQ_DATASET_ID           - BigQuery dataset ID (default: piyolog_raw)
    BQ_TABLE_ID             - BigQuery table ID (default: daily_export_files)
    DRIVE_CHILD_FOLDERS     - JSON mapping child_name -> Drive folder ID (required)
                              e.g. '{"みのり": "1ABC...", "あきら": "1DEF..."}'
    GOOGLE_APPLICATION_CREDENTIALS - path to service account JSON (optional if running on GCP)
"""

import logging
import sys

import google.auth
from google.cloud import bigquery

from piyolog import bq, drive
from piyolog.config import Config

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)


def main() -> None:
    config = Config()
    log.info("Starting ぴよログ raw layer ingestion")
    log.info("BQ target: %s", config.bq_table_ref)
    log.info("Children: %s", list(config.drive_child_folders.keys()))

    credentials, _ = google.auth.default(
        scopes=["https://www.googleapis.com/auth/drive.readonly"]
    )
    drive_service = drive.build_drive_service(credentials)
    bq_client = bigquery.Client(project=config.bq_project_id)

    bq.ensure_dataset_and_table(
        bq_client, config.bq_project_id, config.bq_dataset_id, config.bq_table_id
    )

    total_processed = 0
    total_errors = 0

    for child_name, folder_id in config.drive_child_folders.items():
        log.info("[%s] Listing files in folder %s", child_name, folder_id)
        try:
            files = drive.list_piyolog_files(drive_service, folder_id)
        except Exception as e:
            log.error("[%s] Failed to list files: %s", child_name, e)
            total_errors += 1
            continue

        log.info("[%s] Found %d file(s)", child_name, len(files))

        for file_meta in files:
            file_name = file_meta["name"]
            file_id = file_meta["id"]
            try:
                source_year_month = drive.parse_year_month_from_filename(file_name)
            except ValueError as e:
                log.warning("[%s] Skipping %s: %s", child_name, file_name, e)
                continue

            log.info("[%s] Processing %s (%s)", child_name, file_name, source_year_month)

            try:
                content = drive.download_file_content(drive_service, file_id)
            except Exception as e:
                log.error("[%s] Failed to download %s: %s", child_name, file_name, e)
                total_errors += 1
                continue

            try:
                bq.upsert_record(
                    client=bq_client,
                    project=config.bq_project_id,
                    dataset_id=config.bq_dataset_id,
                    table_id=config.bq_table_id,
                    child_name=child_name,
                    source_year_month=source_year_month,
                    file_name=file_name,
                    drive_file_id=file_id,
                    raw_content=content,
                    loaded_at=bq.utcnow(),
                )
                log.info("[%s] Loaded %s -> BQ (%d chars)", child_name, file_name, len(content))
                total_processed += 1
            except Exception as e:
                log.error("[%s] Failed to upsert %s: %s", child_name, file_name, e)
                total_errors += 1

    log.info("Done. processed=%d errors=%d", total_processed, total_errors)

    if total_errors > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
