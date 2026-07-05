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

variable "staging_dataset_id" {
  type        = string
  description = "dbt staging層データセットID (dbt の generate_schema_name 規則 <profile dataset>_<+schema> に合わせる)"
  default     = "piyolog_staging"
}

variable "intermediate_dataset_id" {
  type        = string
  description = "dbt intermediate層データセットID"
  default     = "piyolog_intermediate"
}

variable "marts_dataset_id" {
  type        = string
  description = "dbt marts層データセットID"
  default     = "piyolog_marts"
}
