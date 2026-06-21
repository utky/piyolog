variable "project_id" {
  type        = string
  description = "Google Cloud のプロジェクトID"
}

variable "region" {
  type        = string
  description = "リソースを作成するリージョン"
}

variable "app_name" {
  type        = string
  description = "アプリケーション名"
  default     = "piyolog"
}

variable "container_image" {
  type        = string
  description = "raw層取り込みジョブのコンテナイメージ"
}

variable "dataset_id" {
  type        = string
  description = "BigQuery データセットID (tf/modules/bigquery の出力を渡す)"
}

variable "table_id" {
  type        = string
  description = "raw層テーブルID (tf/modules/bigquery の出力を渡す)"
}

variable "drive_child_folders" {
  type        = string
  description = "child_name -> Drive フォルダID の JSON マップ"
  # NOTE: sensitive はterraform plan/apply CLI出力上の表示を抑えるのみ。
  # Cloud Run Job では Secret Manager 経由ではない通常の env として渡るため、
  # `gcloud run jobs describe` や Terraform state からは平文で参照できる。
  # Drive フォルダIDは漏洩しても実害が小さいためこの運用で許容する。
  sensitive = true
}

variable "log_level" {
  type        = string
  description = "ログレベル"
  default     = "INFO"
}
