# raw 層データセット
resource "google_bigquery_dataset" "raw" {
  project                    = var.project_id
  dataset_id                 = var.dataset_id
  friendly_name              = "piyolog raw layer"
  description                = "ぴよログ月次エクスポートのテキスト全文を1ファイル1レコードで保持するraw層"
  location                   = var.location
  delete_contents_on_destroy = false
}

# export_files テーブル
# 洗い替え単位は (child_name, source_year_month) であり job 側で MERGE する。
# テーブル自体はここで事前 provision し、job はスキーマ変更を行わない。
resource "google_bigquery_table" "export_files" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.raw.dataset_id
  table_id            = var.table_id
  deletion_protection = true
  description         = "ぴよログ月次エクスポートファイルの全文保持テーブル"

  lifecycle {
    prevent_destroy = true
  }

  schema = jsonencode([
    {
      name        = "child_name"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "Drive フォルダ名に基づく子供の識別名"
    },
    {
      name        = "source_year_month"
      type        = "DATE"
      mode        = "REQUIRED"
      description = "エクスポート対象の年月(月初日)"
    },
    {
      name        = "file_name"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "Drive 上のファイル名"
    },
    {
      name        = "drive_file_id"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "Drive ファイルID"
    },
    {
      name        = "raw_content"
      type        = "STRING"
      mode        = "REQUIRED"
      description = "ファイル本文の全文"
    },
    {
      name        = "loaded_at"
      type        = "TIMESTAMP"
      mode        = "REQUIRED"
      description = "BQ への取り込み時刻"
    },
  ])
}
