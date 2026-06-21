terraform {
  required_version = ">= 1.6.0"

  required_providers {
    google = {
      source = "hashicorp/google"
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

module "scheduler" {
  source     = "../../modules/scheduler"
  project_id = var.project_id
  region     = var.region
  job_name   = module.cloud_run_job.job_name
}
