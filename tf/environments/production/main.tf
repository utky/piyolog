terraform {
  required_version = ">= 1.6.0"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 6.0"
    }
  }

  backend "gcs" {
    # このバケットは事前に手動で作成しておく必要があります
    bucket = "lofilab-piyolog-tfstate"
    prefix = "terraform/state/production"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region

  default_labels = {
    "environment" = "production"
    "managed-by"  = "terraform"
    "repo"        = "piyolog"
    "app"         = "piyolog"
  }
}

module "bigquery" {
  source     = "../../modules/bigquery"
  project_id = var.project_id
  location   = var.region
}

module "cloud_run_job" {
  source              = "../../modules/cloud_run_job"
  project_id          = var.project_id
  region              = var.region
  container_image     = var.container_image
  dataset_id          = module.bigquery.dataset_id
  table_id            = module.bigquery.table_id
  drive_child_folders = var.drive_child_folders
}

module "dbt_job" {
  source          = "../../modules/dbt_job"
  project_id      = var.project_id
  region          = var.region
  container_image = var.dbt_container_image
  raw_dataset_id  = module.bigquery.dataset_id
  dbt_dataset_ids = [
    module.bigquery.staging_dataset_id,
    module.bigquery.intermediate_dataset_id,
    module.bigquery.marts_dataset_id,
  ]
}

# 日次パイプライン: Scheduler -> Workflow -> importer -> dbt (ADR-0010)
module "orchestration" {
  source            = "../../modules/orchestration"
  project_id        = var.project_id
  region            = var.region
  importer_job_name = module.cloud_run_job.job_name
  dbt_job_name      = module.dbt_job.job_name
}

# 旧 scheduler モジュール (Scheduler -> importer 直接呼び出し) からの移行。
# Scheduler SA は作り直さずに引き継ぐ。Scheduler ジョブ自体は名前と呼び出し先が変わるため再作成される。
moved {
  from = module.scheduler.google_service_account.scheduler
  to   = module.orchestration.google_service_account.scheduler
}
