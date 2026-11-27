output "workflow_name" {
  value       = google_workflows_workflow.daily.name
  description = "日次パイプライン Workflow名"
}

output "scheduler_name" {
  value       = google_cloud_scheduler_job.daily.name
  description = "Cloud Scheduler Job名"
}

output "scheduler_sa_email" {
  value       = google_service_account.scheduler.email
  description = "Scheduler用サービスアカウントのメールアドレス"
}
