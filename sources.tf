resource "google_storage_bucket" "sources_bucket" {
  name     = var.sources_bucket_name
  location = "us-east1"
  uniform_bucket_level_access = true
}