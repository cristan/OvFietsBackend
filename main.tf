provider "google" {
  project     = var.project_id
  region      = "europe-west4"
}

resource "google_storage_bucket" "public_bucket" {
  name     = var.public_bucket_name
  location = "europe-west4"
  uniform_bucket_level_access = true
}

resource "google_storage_bucket_iam_member" "public_access" {
  bucket = google_storage_bucket.public_bucket.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}

# Just upload the file via Terraform for now.
# Hosts it at https://storage.googleapis.com/${var.bucket_name}/locations.json
resource "google_storage_bucket_object" "locations_json" {
  name   = "locations.json"  # Object name in the bucket
  bucket = google_storage_bucket.public_bucket.name
  source = "OVfiets/combined_data.json"  # Local path to your JSON file
  content_type = "application/json"
}

resource "google_storage_bucket" "sources_bucket" {
  name     = var.sources_bucket_name
  location = "europe-west4"
  uniform_bucket_level_access = true
}

# Upload script to the bucket so it can be added to the VM via terraform
resource "google_storage_bucket_object" "script" {
   name   = "zmq_subscriber.py"
   bucket = google_storage_bucket.sources_bucket.name
   source = "zmq_subscriber.py"
}