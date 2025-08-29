resource "google_service_account" "python_vm_service_account" {
  account_id   = "python-vm-service-account"
  display_name = "Python VM service account"
}

resource "tls_private_key" "vm_ssh_key" {
  algorithm = "RSA"
  rsa_bits  = 2048
}

resource "google_compute_instance" "python_vm" {
  name         = "python-vm-instance"
  machine_type = "e2-micro"
  # As of writing this code, only 3 regions are free tier eligeable: us-west1, us-central1, us-east1. 
  # Source: https://cloud.google.com/free/docs/free-cloud-features#compute
  # Let's pick us-east1 as it's the closed to the Netherlands
  zone         = "us-east1-b"
  depends_on = [ google_service_account.python_vm_service_account ]

  metadata = {
    ssh-keys = "debian:${tls_private_key.vm_ssh_key.public_key_openssh}"
  }

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
  
  metadata_startup_script = <<-EOF
echo "Starting startup script"
set -x  # Print the commands we're running for extra clarity

# Disable man updating to remove the slow "Processing triggers for man-db"
sudo rm -f /var/lib/man-db/auto-update

PUBLIC_BUCKET_NAME=${var.public_bucket_name}
export PUBLIC_BUCKET_NAME
apt-get update
apt-get install -y python3 python3-pip logrotate
pip3 install --upgrade pip
# TODO: Try pip install -r requirements.txt. This prevents having to note the dependencies twice.
pip3 install pyzmq google-cloud-storage google-cloud-firestore

echo "Finished running startup script. Running the script."

# Tag logs with the tag zmq_subscriber
nohup python3 -u /home/debian/zmq_subscriber.py 2>&1 | logger -t zmq_subscriber &
EOF

  # Note that the VM won't redeploy when files change, so for now, you need to for example manually delete your VM to deploy the changed file.
  # The better solution is to separate the architecture from the code. PR's welcome.
  provisioner "file" {
    source      = "zmq_subscriber.py"
    destination = "/home/debian/zmq_subscriber.py"
  }

  provisioner "file" {
    source      = "firestore_history.py"
    destination = "/home/debian/firestore_history.py"
  }

  provisioner "file" {
    source      = "overview_bucket.py"
    destination = "/home/debian/overview_bucket.py"
  }

  connection {
      type        = "ssh"
      user        = "debian"
      private_key = tls_private_key.vm_ssh_key.private_key_pem
      host        = self.network_interface[0].access_config[0].nat_ip
  }
}

resource "google_storage_bucket_iam_binding" "allow_vm_write_bucket" {
  bucket = var.public_bucket_name

  role    = "roles/storage.objectAdmin"
  members = [
    "serviceAccount:${google_service_account.python_vm_service_account.email}"
  ]
}

resource "google_project_iam_member" "allow_vm_firestore" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.python_vm_service_account.email}"
}