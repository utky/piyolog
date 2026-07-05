output "dataset_id" {
  value       = google_bigquery_dataset.raw.dataset_id
  description = "BigQuery データセットID"
}

output "table_id" {
  value       = google_bigquery_table.export_files.table_id
  description = "raw層テーブルID"
}

output "staging_dataset_id" {
  value       = google_bigquery_dataset.staging.dataset_id
  description = "dbt staging層データセットID"
}

output "intermediate_dataset_id" {
  value       = google_bigquery_dataset.intermediate.dataset_id
  description = "dbt intermediate層データセットID"
}

output "marts_dataset_id" {
  value       = google_bigquery_dataset.marts.dataset_id
  description = "dbt marts層データセットID"
}
