# raw層取り込みジョブ用サービスアカウント
resource "google_service_account" "raw_layer" {
  project      = var.project_id
  account_id   = "${var.app_name}-raw-layer-sa"
  display_name = "Service Account for piyolog raw layer Cloud Run Job"
}

# BigQuery データ編集権限
resource "google_project_iam_member" "raw_layer_bigquery_data_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.raw_layer.email}"
}

# BigQuery ジョブ実行権限
resource "google_project_iam_member" "raw_layer_bigquery_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.raw_layer.email}"
}

# Cloud Run Job
# Drive フォルダへのアクセスは IAM では付与できないため、
# このSAのメールアドレスを Drive フォルダ側で手動共有設定する必要がある(運用手順)。
resource "google_cloud_run_v2_job" "raw_layer" {
  name                = "${var.app_name}-raw-layer"
  location            = var.region
  deletion_protection = false

  template {
    template {
      service_account = google_service_account.raw_layer.email
      timeout         = "300s"

      containers {
        image = var.container_image

        resources {
          limits = {
            memory = "256Mi"
            cpu    = "1"
          }
        }

        env {
          name  = "BQ_PROJECT_ID"
          value = var.project_id
        }

        env {
          name  = "BQ_DATASET_ID"
          value = var.dataset_id
        }

        env {
          name  = "BQ_TABLE_ID"
          value = var.table_id
        }

        env {
          name  = "DRIVE_CHILD_FOLDERS"
          value = var.drive_child_folders
        }

        env {
          name  = "LOG_LEVEL"
          value = var.log_level
        }
      }
    }
  }
}
