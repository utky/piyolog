variable "project_id" {
  type        = string
  description = "Google Cloud のプロジェクトID"
}

variable "location" {
  type        = string
  description = "BigQuery データセットのロケーション"
  default     = "asia-northeast1"
}

variable "dataset_id" {
  type        = string
  description = "BigQuery データセットID"
  default     = "piyolog_raw"
}

variable "table_id" {
  type        = string
  description = "raw層テーブルID"
  default     = "export_files"
}
