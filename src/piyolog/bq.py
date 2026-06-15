"""BigQuery operations for the ぴよログ raw layer."""

from datetime import date, datetime, timezone

from google.cloud import bigquery


def verify_table_exists(
    client: bigquery.Client, project: str, dataset_id: str, table_id: str
) -> None:
    """Verify the target table exists; raise RuntimeError if not.

    Dataset and table must be provisioned in advance via OpenTofu.
    """
    table_ref = f"{project}.{dataset_id}.{table_id}"
    try:
        client.get_table(table_ref)
    except Exception as e:
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


def merge_record(
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
    """Upsert a single file record using MERGE keyed on (child_name, source_year_month)."""
    table_ref = f"`{project}.{dataset_id}.{table_id}`"
    sym_date = source_year_month.isoformat()

    merge_sql = f"""
        MERGE {table_ref} AS T
        USING (
            SELECT
                @child_name          AS child_name,
                @source_year_month   AS source_year_month,
                @file_name           AS file_name,
                @drive_file_id       AS drive_file_id,
                @raw_content         AS raw_content,
                @loaded_at           AS loaded_at
        ) AS S
        ON T.child_name = S.child_name
           AND T.source_year_month = S.source_year_month
        WHEN MATCHED THEN
            UPDATE SET
                file_name      = S.file_name,
                drive_file_id  = S.drive_file_id,
                raw_content    = S.raw_content,
                loaded_at      = S.loaded_at
        WHEN NOT MATCHED THEN
            INSERT (child_name, source_year_month, file_name, drive_file_id, raw_content, loaded_at)
            VALUES (S.child_name, S.source_year_month, S.file_name,
                    S.drive_file_id, S.raw_content, S.loaded_at)
    """
    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ScalarQueryParameter("child_name", "STRING", child_name),
            bigquery.ScalarQueryParameter("source_year_month", "DATE", sym_date),
            bigquery.ScalarQueryParameter("file_name", "STRING", file_name),
            bigquery.ScalarQueryParameter("drive_file_id", "STRING", drive_file_id),
            bigquery.ScalarQueryParameter("raw_content", "STRING", raw_content),
            bigquery.ScalarQueryParameter("loaded_at", "TIMESTAMP", loaded_at.isoformat()),
        ]
    )
    client.query(merge_sql, job_config=job_config).result()


def utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)
