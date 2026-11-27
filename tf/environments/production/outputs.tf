output "bigquery_dataset_id" {
  value       = module.bigquery.dataset_id
  description = "BigQuery raw層データセットID"
}

output "importer_job_name" {
  value       = module.cloud_run_job.job_name
  description = "取り込み Cloud Run Job名"
}

output "importer_service_account_email" {
  value       = module.cloud_run_job.service_account_email
  description = "取り込みジョブ用SA。Driveフォルダの共有設定に使用する"
}

output "dbt_job_name" {
  value       = module.dbt_job.job_name
  description = "dbt Cloud Run Job名"
}

output "dbt_service_account_email" {
  value       = module.dbt_job.service_account_email
  description = "dbt ジョブ用SA"
}

output "workflow_name" {
  value       = module.orchestration.workflow_name
  description = "日次パイプライン Workflow名"
}

output "scheduler_name" {
  value       = module.orchestration.scheduler_name
  description = "Cloud Scheduler Job名"
}
