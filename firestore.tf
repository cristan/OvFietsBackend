resource "google_firestore_database" "default" {
  project     = var.project_id
  name        = "(default)"
  # The Netherlands. There is no limitation on region for the free tier, so let's pick the one closest to our users
  location_id = "europe-west4"
  type        = "FIRESTORE_NATIVE"
}