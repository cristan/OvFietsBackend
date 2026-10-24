provider "google" {
  alias   = "billing"
  project = var.project_id
  # The Billing Budgets API refuses user credentials unless a quota project is set
  user_project_override = true
  billing_project       = var.project_id
}

resource "google_project_service" "billing_budgets" {
  project            = var.project_id
  service            = "billingbudgets.googleapis.com"
  disable_on_destroy = false
}

data "google_project" "project" {}

resource "google_billing_budget" "monthly" {
  provider        = google.billing
  billing_account = var.billing_account_id
  display_name    = "OV-fiets monthly costs"

  budget_filter {
    projects = ["projects/${data.google_project.project.number}"]
  }

  amount {
    specified_amount {
      currency_code = "EUR"
      units         = "2"
    }
  }

  threshold_rules {
    threshold_percent = 1.0
  }

  threshold_rules {
    threshold_percent = 1.0
    spend_basis       = "FORECASTED_SPEND"
  }

  depends_on = [google_project_service.billing_budgets]
}
