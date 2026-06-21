output "bigquery_dataset_id" {
  value       = module.bigquery.dataset_id
  description = "BigQuery raw層データセットID"
}

output "raw_layer_job_name" {
  value       = module.cloud_run_job.job_name
  description = "raw層取り込み Cloud Run Job名"
}

output "raw_layer_service_account_email" {
  value       = module.cloud_run_job.service_account_email
  description = "raw層取り込みジョブ用SA。Driveフォルダの共有設定に使用する"
}

output "scheduler_name" {
  value       = module.scheduler.scheduler_name
  description = "Cloud Scheduler Job名"
}
