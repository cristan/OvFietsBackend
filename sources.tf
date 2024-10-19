resource "google_storage_bucket" "sources_bucket" {
  name     = var.sources_bucket_name
  location = "us-east1"
  uniform_bucket_level_access = true
}

# Upload script to the bucket so it can be added to the VM via terraform
resource "google_storage_bucket_object" "script" {
   name   = "zmq_subscriber.py"
   bucket = google_storage_bucket.sources_bucket.name
   source = "zmq_subscriber.py"
}