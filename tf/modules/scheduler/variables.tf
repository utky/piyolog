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

variable "job_name" {
  type        = string
  description = "raw層取り込み Cloud Run Job名"
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
