# 日次パイプライン: Cloud Scheduler -> Workflows -> (importer job -> dbt job)  (ADR-0010)

# --- Workflow ---------------------------------------------------------------

resource "google_service_account" "workflow" {
  project      = var.project_id
  account_id   = "${var.app_name}-workflow-sa"
  display_name = "Service Account for piyolog daily Workflow"
}

# 各 Cloud Run job の実行権限 (run.jobs.run)。overrides を使わないので invoker で足りる
resource "google_cloud_run_v2_job_iam_member" "workflow_invoker" {
  for_each = toset(local.job_names)

  project  = var.project_id
  location = var.region
  name     = each.value
  role     = "roles/run.invoker"
  member   = "serviceAccount:${google_service_account.workflow.email}"
}

# jobs.run コネクタが実行完了まで long-running operation / execution をポーリングするための読み取り権限
resource "google_project_iam_member" "workflow_run_viewer" {
  project = var.project_id
  role    = "roles/run.viewer"
  member  = "serviceAccount:${google_service_account.workflow.email}"
}

# sys.log / コールログの書き込み
resource "google_project_iam_member" "workflow_log_writer" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.workflow.email}"
}

resource "google_workflows_workflow" "daily" {
  project         = var.project_id
  name            = "${var.app_name}-daily"
  region          = var.region
  description     = "piyolog 日次パイプライン (importer -> dbt build)"
  service_account = google_service_account.workflow.id
  call_log_level  = "LOG_ERRORS_ONLY"
  source_contents = file("${path.module}/workflow.yaml")

  user_env_vars = {
    IMPORTER_JOB = var.importer_job_name
    DBT_JOB      = var.dbt_job_name
  }

  deletion_protection = false
}

# --- Scheduler --------------------------------------------------------------

resource "google_service_account" "scheduler" {
  project      = var.project_id
  account_id   = "${var.app_name}-scheduler-sa"
  display_name = "Service Account for piyolog importer Cloud Scheduler"
}

resource "google_project_iam_member" "scheduler_workflows_invoker" {
  project = var.project_id
  role    = "roles/workflows.invoker"
  member  = "serviceAccount:${google_service_account.scheduler.email}"
}

# 日次1回、Workflow の実行を作成する
resource "google_cloud_scheduler_job" "daily" {
  name             = "${var.app_name}-daily"
  description      = "piyolog 日次パイプライン (Workflow) を起動"
  schedule         = var.schedule
  time_zone        = var.time_zone
  region           = var.region
  attempt_deadline = "180s"

  http_target {
    http_method = "POST"
    uri         = "https://workflowexecutions.googleapis.com/v1/${google_workflows_workflow.daily.id}/executions"
    body        = base64encode(jsonencode({}))
    headers = {
      "Content-Type" = "application/json"
    }
    oauth_token {
      service_account_email = google_service_account.scheduler.email
      scope                 = "https://www.googleapis.com/auth/cloud-platform"
    }
  }

  depends_on = [google_project_iam_member.scheduler_workflows_invoker]
}
