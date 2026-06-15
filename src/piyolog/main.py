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

    bq.verify_table_exists(
        bq_client, config.bq_project_id, config.bq_dataset_id, config.bq_table_id
    )

    total_processed = 0

    for child_name, folder_id in config.drive_child_folders.items():
        log.info("[%s] Listing files in folder %s", child_name, folder_id)
        files = drive.list_piyolog_files(drive_service, folder_id)
        log.info("[%s] Found %d file(s)", child_name, len(files))

        loaded_at_map = bq.fetch_loaded_at(
            bq_client, config.bq_project_id, config.bq_dataset_id, config.bq_table_id, child_name
        )

        for drive_file in files:
            try:
                source_year_month = drive.parse_year_month_from_filename(drive_file.name)
            except ValueError as e:
                log.warning("[%s] Skipping %s: %s", child_name, drive_file.name, e)
                continue

            existing_loaded_at = loaded_at_map.get(source_year_month)
            if existing_loaded_at is not None and drive_file.modified_at <= existing_loaded_at:
                log.info(
                    "[%s] Skipping %s (not modified since last load)",
                    child_name, drive_file.name,
                )
                continue

            log.info("[%s] Processing %s (%s)", child_name, drive_file.name, source_year_month)
            content = drive.download_file_content(drive_service, drive_file.file_id)
            bq.merge_record(
                client=bq_client,
                project=config.bq_project_id,
                dataset_id=config.bq_dataset_id,
                table_id=config.bq_table_id,
                child_name=child_name,
                source_year_month=source_year_month,
                file_name=drive_file.name,
                drive_file_id=drive_file.file_id,
                raw_content=content,
                loaded_at=bq.utcnow(),
            )
            log.info("[%s] Loaded %s -> BQ (%d chars)", child_name, drive_file.name, len(content))
            total_processed += 1

    log.info("Done. processed=%d", total_processed)


if __name__ == "__main__":
    main()
