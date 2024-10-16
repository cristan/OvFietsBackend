variable "project_id" {
  description = "The GCP project ID"
  type        = string
}

variable "public_bucket_name" {
  description = "The name of the bucket where public files will be located"
  type        = string
}

variable "sources_bucket_name" {
  description = "The name of the bucket where source files will be placed"
  type        = string
}