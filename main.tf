provider "google" {
  project     = var.project_id
  region      = "us-east1"
}

resource "google_storage_bucket" "public_bucket" {
  name     = var.public_bucket_name
  location = "us-east1"
  uniform_bucket_level_access = true
}

resource "google_storage_bucket_iam_member" "public_access" {
  bucket = google_storage_bucket.public_bucket.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}