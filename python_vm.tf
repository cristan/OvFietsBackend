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
set -x  # Enable debugging
exec > /var/log/startup-script.log 2>&1 # Redirect all output to this log file

echo "Starting startup script"
PUBLIC_BUCKET_NAME=${var.public_bucket_name}
export PUBLIC_BUCKET_NAME
apt-get update
apt-get install -y python3 python3-pip logrotate
pip3 install --upgrade pip
pip3 install pyzmq google-cloud-storage

echo "Finished running startup script. Running the script."

# Use a different log file for the actual script
exec > /var/log/zmq_subscriber.log 2>&1
nohup python3 /home/debian/zmq_subscriber.py
EOF

  # Note that the VM won't redeploy when files change, so for now, you need to for example manually delete your VM to deploy the changed file.
  # The better solution is to separate the architecture from the code. PR's welcome.
  provisioner "file" {
    source      = "zmq_subscriber.py"
    destination = "/home/debian/zmq_subscriber.py"
  }

  provisioner "file" {
    source      = "logrotate/zmq_subscriber"
    destination = "/home/debian/zmq_subscriber"
  }
  provisioner "remote-exec" {
    inline = [
      "sudo mv /home/debian/zmq_subscriber /etc/logrotate.d/zmq_subscriber",
      "sudo chown root:root /etc/logrotate.d/zmq_subscriber",
    ]
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
