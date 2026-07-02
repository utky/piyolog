# 取り込みジョブ用サービスアカウント
resource "google_service_account" "importer" {
  project      = var.project_id
  account_id   = "${var.app_name}-importer-sa"
  display_name = "Service Account for piyolog importer Cloud Run Job"
}

# BigQuery データ編集権限
resource "google_project_iam_member" "importer_bigquery_data_editor" {
  project = var.project_id
  role    = "roles/bigquery.dataEditor"
  member  = "serviceAccount:${google_service_account.importer.email}"
}

# BigQuery ジョブ実行権限
resource "google_project_iam_member" "importer_bigquery_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.importer.email}"
}

# DRIVE_CHILD_FOLDERS シークレット
# child_name キーに子供の個人名が入るため Secret Manager で管理する。
# secretmanager.googleapis.com の有効化は lofilab 側 tf で行う。
resource "google_secret_manager_secret" "drive_child_folders" {
  project   = var.project_id
  secret_id = "${var.app_name}-drive-child-folders"

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret_version" "drive_child_folders" {
  secret      = google_secret_manager_secret.drive_child_folders.id
  secret_data = var.drive_child_folders
}

resource "google_secret_manager_secret_iam_member" "importer_accessor" {
  project   = var.project_id
  secret_id = google_secret_manager_secret.drive_child_folders.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${google_service_account.importer.email}"
}

# Cloud Run Job
# Drive フォルダへのアクセスは IAM では付与できないため、
# このSAのメールアドレスを Drive フォルダ側で手動共有設定する必要がある(運用手順)。
resource "google_cloud_run_v2_job" "importer" {
  name                = "${var.app_name}-importer"
  location            = var.region
  deletion_protection = false

  template {
    template {
      service_account = google_service_account.importer.email
      timeout         = "300s"

      containers {
        image = var.container_image

        resources {
          limits = {
            memory = "512Mi"
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
          name = "DRIVE_CHILD_FOLDERS"
          value_source {
            secret_key_ref {
              secret  = google_secret_manager_secret.drive_child_folders.secret_id
              version = "latest"
            }
          }
        }

        env {
          name  = "LOG_LEVEL"
          value = var.log_level
        }
      }
    }
  }

  depends_on = [google_secret_manager_secret_version.drive_child_folders]
}
