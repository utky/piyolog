# Scheduler 用 SA
resource "google_service_account" "scheduler" {
  project      = var.project_id
  account_id   = "${var.app_name}-scheduler-sa"
  display_name = "Service Account for piyolog raw layer Cloud Scheduler"
}

# Scheduler SA → raw層 Cloud Run Job の実行権限
# overrides を使わないため roles/run.developer ではなく roles/run.invoker で十分
resource "google_cloud_run_v2_job_iam_member" "scheduler_invoker" {
  project  = var.project_id
  location = var.region
  name     = var.job_name
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.scheduler.email}"
}

# Cloud Scheduler: 日次1回、Cloud Run Jobs API を直接呼び出す
# 単一ジョブ・引数オーバーライド不要のため Cloud Workflows は介さない
resource "google_cloud_scheduler_job" "raw_layer_daily" {
  name             = "${var.app_name}-raw-layer-daily"
  description      = "piyolog raw層取り込みジョブを日次で実行"
  schedule         = var.schedule
  time_zone        = var.time_zone
  region           = var.region
  attempt_deadline = "600s"

  http_target {
    http_method = "POST"
    uri         = "https://run.googleapis.com/v2/projects/${var.project_id}/locations/${var.region}/jobs/${var.job_name}:run"
    oauth_token {
      service_account_email = google_service_account.scheduler.email
    }
  }
}
