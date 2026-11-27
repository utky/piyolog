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

variable "importer_job_name" {
  type        = string
  description = "取り込み Cloud Run Job名 (Workflow の1段目)"
}

variable "dbt_job_name" {
  type        = string
  description = "dbt Cloud Run Job名 (Workflow の2段目)"
}

variable "schedule" {
  type        = string
  description = "cron形式の実行スケジュール"
  default     = "0 6 * * *"
}

variable "time_zone" {
  type        = string
  description = "スケジュールのタイムゾーン"
  default     = "Asia/Tokyo"
}

locals {
  job_names = [var.importer_job_name, var.dbt_job_name]
}
