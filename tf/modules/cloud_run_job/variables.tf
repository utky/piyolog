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
  description = "取り込みジョブのコンテナイメージ"
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
  description = "child_name -> Drive フォルダID の JSON マップ (child_name に子供の個人名が入るため Secret Manager で管理)"
  sensitive   = true
}

variable "log_level" {
  type        = string
  description = "ログレベル"
  default     = "INFO"
}
