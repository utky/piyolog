output "dataset_id" {
  value       = google_bigquery_dataset.raw.dataset_id
  description = "BigQuery データセットID"
}

output "table_id" {
  value       = google_bigquery_table.export_files.table_id
  description = "raw層テーブルID"
}
