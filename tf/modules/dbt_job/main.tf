# dbt build 実行ジョブ用サービスアカウント (ADR-0010)
resource "google_service_account" "dbt" {
  project      = var.project_id
  account_id   = "${var.app_name}-dbt-sa"
  display_name = "Service Account for piyolog dbt Cloud Run Job"
}

# BigQuery ジョブ実行権限 (クエリ・DDL の実行)
resource "google_project_iam_member" "dbt_bigquery_job_user" {
  project = var.project_id
  role    = "roles/bigquery.jobUser"
  member  = "serviceAccount:${google_service_account.dbt.email}"
}

# raw 層は dbt の source なので読み取りのみ
resource "google_bigquery_dataset_iam_member" "dbt_raw_viewer" {
  project    = var.project_id
  dataset_id = var.raw_dataset_id
  role       = "roles/bigquery.dataViewer"
  member     = "serviceAccount:${google_service_account.dbt.email}"
}

# dbt が構築するデータセット (view/table/UDF の作成・置換)
resource "google_bigquery_dataset_iam_member" "dbt_editor" {
  for_each = toset(var.dbt_dataset_ids)

  project    = var.project_id
  dataset_id = each.value
  role       = "roles/bigquery.dataEditor"
  member     = "serviceAccount:${google_service_account.dbt.email}"
}

resource "google_cloud_run_v2_job" "dbt" {
  name                = "${var.app_name}-dbt"
  location            = var.region
  deletion_protection = false

  template {
    template {
      service_account = google_service_account.dbt.email
      timeout         = "900s"
      # dbt build の失敗はデータ/テストの問題であることが多く、即時リトライしても直らない
      max_retries = 0

      containers {
        image = var.container_image

        resources {
          limits = {
            memory = "1Gi"
            cpu    = "1"
          }
        }

        env {
          name  = "BQ_PROJECT_ID"
          value = var.project_id
        }
      }
    }
  }

  # CI (deploy.yml) の `gcloud run jobs update` が書き込むメタデータ。Terraform 管理外なので差分にしない
  lifecycle {
    ignore_changes = [client, client_version]
  }
}
