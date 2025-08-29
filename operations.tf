module "cloud-operations_ops-agent-policy" {
  source  = "terraform-google-modules/cloud-operations/google//modules/ops-agent-policy"
  version = "~> 0.6.0"

  project       = var.project_id
  assignment_id = "ops-agents-zmq-subscriber"
  zone          = "us-east1-b"

  # Target only VMs with the ops-agent label
  instance_filter = {
    inclusion_labels = [{
      labels = {
        ops-agent = "true"
      }
    }]
  }

  depends_on = [
    google_project_service.apis,
    google_project_iam_member.vm_sa_logging,
    google_project_iam_member.vm_sa_monitoring,
  ]
}

resource "google_project_iam_member" "vm_sa_logging" {
  project = var.project_id
  role    = "roles/logging.logWriter"
  member  = "serviceAccount:${google_service_account.python_vm_service_account.email}"
}

resource "google_project_iam_member" "vm_sa_monitoring" {
  project = var.project_id
  role    = "roles/monitoring.metricWriter"
  member  = "serviceAccount:${google_service_account.python_vm_service_account.email}"
}