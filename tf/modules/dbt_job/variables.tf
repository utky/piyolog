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
  description = "dbt ジョブのコンテナイメージ"
}

variable "raw_dataset_id" {
  type        = string
  description = "dbt の source となる raw 層データセットID (読み取りのみ)"
}

variable "dbt_dataset_ids" {
  type        = list(string)
  description = "dbt が構築するデータセットID (staging / intermediate / marts)"
}
