variable "project_id" {
  type        = string
  description = "Google Cloud のプロジェクトID"
  default     = "lofilab"
}

variable "region" {
  type        = string
  description = "リソースを作成するリージョン"
  default     = "asia-northeast1"
}

variable "container_image" {
  type        = string
  description = "取り込みジョブのコンテナイメージ"
  default     = "asia-northeast1-docker.pkg.dev/lofilab/utky-applications/piyolog-importer:latest"
}

variable "drive_child_folders" {
  type        = string
  description = "child_name -> Drive フォルダID の JSON マップ"
  sensitive   = true
}
