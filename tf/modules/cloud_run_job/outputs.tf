output "job_name" {
  value       = google_cloud_run_v2_job.raw_layer.name
  description = "Cloud Run Job名"
}

output "service_account_email" {
  value       = google_service_account.raw_layer.email
  description = "raw層取り込みジョブ用サービスアカウントのメールアドレス(Driveフォルダ共有設定に使用)"
}
