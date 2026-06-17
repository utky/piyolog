"""BigQuery operations for the ぴよログ raw layer."""

import uuid
from dataclasses import dataclass
from datetime import date, datetime, timezone

from google.api_core.exceptions import NotFound
from google.cloud import bigquery

SCHEMA = [
    bigquery.SchemaField("child_name", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("source_year_month", "DATE", mode="REQUIRED"),
    bigquery.SchemaField("file_name", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("drive_file_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("raw_content", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("loaded_at", "TIMESTAMP", mode="REQUIRED"),
]


@dataclass
class ExportRecord:
    child_name: str
    source_year_month: date
    file_name: str
    drive_file_id: str
    raw_content: str
    loaded_at: datetime

    def to_bq_dict(self) -> dict:
        return {
            "child_name": self.child_name,
            "source_year_month": self.source_year_month.isoformat(),
            "file_name": self.file_name,
            "drive_file_id": self.drive_file_id,
            "raw_content": self.raw_content,
            "loaded_at": self.loaded_at.isoformat(),
        }


def verify_table_exists(
    client: bigquery.Client, project: str, dataset_id: str, table_id: str
) -> None:
    """Verify the target table exists; raise RuntimeError if not.

    Dataset and table must be provisioned in advance via OpenTofu.
    """
    table_ref = f"{project}.{dataset_id}.{table_id}"
    try:
        client.get_table(table_ref)
    except NotFound as e:
        raise RuntimeError(
            f"BigQuery table {table_ref!r} not found. "
            "Provision it with OpenTofu before running this job."
        ) from e


def fetch_loaded_at(
    client: bigquery.Client,
    project: str,
    dataset_id: str,
    table_id: str,
    child_name: str,
) -> dict[date, datetime]:
    """Return {source_year_month: loaded_at} for all records of the given child."""
    sql = f"""
        SELECT source_year_month, loaded_at
        FROM `{project}.{dataset_id}.{table_id}`
        WHERE child_name = @child_name
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("child_name", "STRING", child_name),
        ]
    )
    rows = client.query(sql, job_config=job_config).result()
    return {row.source_year_month: row.loaded_at.astimezone(timezone.utc) for row in rows}


def bulk_merge(
    client: bigquery.Client,
    project: str,
    dataset_id: str,
    table_id: str,
    records: list[ExportRecord],
) -> None:
    """Load records into a temporary table then MERGE into the target in a single query.

    Using a temp table avoids query parameter size limits from large raw_content strings.
    The temp table is always deleted in the finally block.
    """
    if not records:
        return

    tmp_id = f"_tmp_export_{uuid.uuid4().hex}"
    tmp_ref = f"{project}.{dataset_id}.{tmp_id}"
    target_ref = f"`{project}.{dataset_id}.{table_id}`"

    load_job = client.load_table_from_json(
        [r.to_bq_dict() for r in records],
        tmp_ref,
        job_config=bigquery.LoadJobConfig(
            schema=SCHEMA,
            write_disposition="WRITE_TRUNCATE",
        ),
    )
    load_job.result()

    try:
        merge_sql = f"""
            MERGE {target_ref} AS T
            USING `{project}.{dataset_id}.{tmp_id}` AS S
            ON T.child_name = S.child_name
               AND T.source_year_month = S.source_year_month
            WHEN MATCHED THEN
                UPDATE SET
                    file_name     = S.file_name,
                    drive_file_id = S.drive_file_id,
                    raw_content   = S.raw_content,
                    loaded_at     = S.loaded_at
            WHEN NOT MATCHED THEN
                INSERT (child_name, source_year_month, file_name,
                        drive_file_id, raw_content, loaded_at)
                VALUES (S.child_name, S.source_year_month, S.file_name,
                        S.drive_file_id, S.raw_content, S.loaded_at)
        """
        client.query(merge_sql).result()
    finally:
        client.delete_table(tmp_ref, not_found_ok=True)


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)
