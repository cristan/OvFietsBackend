provider "google" {
  project     = var.project_id
  region      = "europe-west4"
}

resource "google_storage_bucket" "bucket" {
  name     = var.bucket_name
  location = "EUROPE-WEST4"

  uniform_bucket_level_access = true

  versioning {
    enabled = false
  }
}

# Just upload the file via Terraform for now.
# Hosts it at https://storage.googleapis.com/${var.bucket_name}/locations.json
resource "google_storage_bucket_object" "combined_data_json" {
  name   = "locations.json"  # Object name in the bucket
  bucket = google_storage_bucket.bucket.name
  source = "OVfiets/combined_data.json"  # Local path to your JSON file
  content_type = "application/json"
}

resource "google_storage_bucket_iam_member" "public_access" {
  bucket = google_storage_bucket.bucket.name
  role   = "roles/storage.objectViewer"
  member = "allUsers"
}

# Upload script to the bucket so it can be added to the VM via terraform
# TODO: do this and check if putting it in another bucket costs more. If no, do that: mixing up internal source code and externally hosted stuff seems bad.
# resource "google_storage_bucket_object" "script" {
#   name   = "zmq_subscriber.py"
#   bucket = google_storage_bucket.bucket.name
#   source = "zmq_subscriber.py"  # Local path to your Python script
# }