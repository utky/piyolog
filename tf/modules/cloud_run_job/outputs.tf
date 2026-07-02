output "job_name" {
  value       = google_cloud_run_v2_job.importer.name
  description = "Cloud Run Job名"
}

output "service_account_email" {
  value       = google_service_account.importer.email
  description = "取り込みジョブ用サービスアカウントのメールアドレス(Driveフォルダ共有設定に使用)"
}
