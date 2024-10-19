resource "google_service_account" "python_vm_service_account" {
  account_id   = "python-vm-service-account"
  display_name = "Python VM service account"
}

resource "google_compute_instance" "python_vm" {
  name         = "python-vm-instance"
  machine_type = "e2-micro"
  # As of writing this code, only 3 regions are free tier eligeable: us-west1, us-central1, us-east1. 
  # Source: https://cloud.google.com/free/docs/free-cloud-features#compute
  # Let's pick us-east1 as it's the closed to the Netherlands
  zone         = "us-east1-b"
  depends_on = [ google_storage_bucket.sources_bucket, google_service_account.python_vm_service_account ]

  boot_disk {
    initialize_params {
      image = "debian-cloud/debian-11"
      # 10 GB storage should be plenty, and keeps us in the free tier (limit: 30GB)
      size  = 10
    }
  }

  service_account {
    email  = google_service_account.python_vm_service_account.email
    scopes = ["cloud-platform"]
  }

  network_interface {
    network = "default"
    access_config {
      # Ephemeral IP
    }
  }

  metadata = {
    PUBLIC_BUCKET_NAME = var.public_bucket_name
  }

  metadata_startup_script = <<-EOF
apt-get update
apt-get install -y python3 python3-pip
pip3 install --upgrade pip
pip3 install zmq
pip3 install google-cloud-storage

gsutil cp gs://${var.sources_bucket_name}/zmq_subscriber.py ~
nohup python3 ~/zmq_subscriber.py
EOF

}

resource "google_storage_bucket_iam_binding" "allow_vm_reading_source_bucket" {
  bucket = var.sources_bucket_name

  role    = "roles/storage.objectViewer"
  members = [
    "serviceAccount:${google_service_account.python_vm_service_account.email}"
  ]
}

resource "google_storage_bucket_iam_binding" "allow_vm_write_bucket" {
  bucket = var.public_bucket_name

  role    = "roles/storage.objectAdmin"
  members = [
    "serviceAccount:${google_service_account.python_vm_service_account.email}"
  ]
}