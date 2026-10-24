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

variable "billing_account_id" {
  description = "The ID of the billing account that pays for the project, used for the budget alert, like 012345-567890-ABCDEF (without billingAccounts/ in front)"
  type        = string
}
