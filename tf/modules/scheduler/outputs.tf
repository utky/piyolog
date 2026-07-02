output "scheduler_name" {
  value       = google_cloud_scheduler_job.importer_daily.name
  description = "Cloud Scheduler Job名"
}

output "scheduler_sa_email" {
  value       = google_service_account.scheduler.email
  description = "Scheduler用サービスアカウントのメールアドレス"
}
