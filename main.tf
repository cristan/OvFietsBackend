provider "google" {
  project     = var.project_id
  # I honestly don't know what this does, as you have to specify a region everywhere anyway.
  # Picked the same region as our python_vm instance is located.
  region      = "us-east1"
}

resource "google_project_service" "apis" {
  for_each = toset([
    "osconfig.googleapis.com",   # OS Config (VM Manager / OSPolicy)
    "logging.googleapis.com",    # Cloud Logging
    "monitoring.googleapis.com", # Cloud Monitoring
  ])
  project             = var.project_id
  service             = each.key
  disable_on_destroy  = false
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