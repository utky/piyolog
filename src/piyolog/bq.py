"""BigQuery operations for the ぴよログ raw layer."""

from datetime import date, datetime, timezone
from typing import Any

from google.cloud import bigquery

SCHEMA = [
    bigquery.SchemaField("child_name", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("source_year_month", "DATE", mode="REQUIRED"),
    bigquery.SchemaField("file_name", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("drive_file_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("raw_content", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("loaded_at", "TIMESTAMP", mode="REQUIRED"),
]


def ensure_dataset_and_table(
    client: bigquery.Client, project: str, dataset_id: str, table_id: str
) -> None:
    """Create the dataset and table if they do not already exist."""
    dataset_ref = bigquery.DatasetReference(project, dataset_id)
    try:
        client.get_dataset(dataset_ref)
    except Exception:
        dataset = bigquery.Dataset(dataset_ref)
        dataset.location = "asia-northeast1"
        client.create_dataset(dataset, exists_ok=True)

    table_ref = bigquery.TableReference(dataset_ref, table_id)
    table = bigquery.Table(table_ref, schema=SCHEMA)
    client.create_table(table, exists_ok=True)


def upsert_record(
    client: bigquery.Client,
    project: str,
    dataset_id: str,
    table_id: str,
    child_name: str,
    source_year_month: date,
    file_name: str,
    drive_file_id: str,
    raw_content: str,
    loaded_at: datetime,
) -> None:
    """Delete existing record for (child_name, source_year_month) then insert new one."""
    table_ref = f"`{project}.{dataset_id}.{table_id}`"
    sym_date = source_year_month.isoformat()

    delete_sql = f"""
        DELETE FROM {table_ref}
        WHERE child_name = @child_name
          AND source_year_month = @source_year_month
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("child_name", "STRING", child_name),
            bigquery.ScalarQueryParameter("source_year_month", "DATE", sym_date),
        ]
    )
    client.query(delete_sql, job_config=job_config).result()

    rows_to_insert: list[dict[str, Any]] = [
        {
            "child_name": child_name,
            "source_year_month": sym_date,
            "file_name": file_name,
            "drive_file_id": drive_file_id,
            "raw_content": raw_content,
            "loaded_at": loaded_at.isoformat(),
        }
    ]
    errors = client.insert_rows_json(
        f"{project}.{dataset_id}.{table_id}", rows_to_insert
    )
    if errors:
        raise RuntimeError(f"BigQuery insert errors for {child_name}/{sym_date}: {errors}")


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)
