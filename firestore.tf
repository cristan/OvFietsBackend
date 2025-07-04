resource "google_firestore_database" "default" {
  project     = var.project_id
  name        = "(default)"
  # The Netherlands. There is no limitation on region for the free tier, so let's pick the one closest to our users
  location_id = "europe-west4"
  type        = "FIRESTORE_NATIVE"
}

resource "google_firestore_field" "hourly_capacity_ttl" {
  project     = var.project_id
  collection  = "hourly_location_capacity"
  field       = "ttl"
  ttl_config { }
}

resource "google_firebaserules_ruleset" "hourly_capacity_public_access" {
  project = var.project_id
  provider    = google-beta

  source {
    files {
      name    = "firestore.rules"
      content = file("firestore.rules")
    }
  }

  depends_on = [
    google_firestore_database.default
  ]
}

// Needs a terraform/tofu import to overwrite the default one. Change imports.tf to get this to work.
resource "google_firebaserules_release" "hourly_capacity_public_access" {
  name         = "cloud.firestore"
  project      = var.project_id
  ruleset_name = google_firebaserules_ruleset.hourly_capacity_public_access.name
}