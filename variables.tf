variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "public_bucket_name" {
  description = "The name of the bucket where public files will be located"
  type        = string
}

variable "history_bucket_name" {
  description = "The name of the private bucket where the history of all readings is stored"
  type        = string
}
