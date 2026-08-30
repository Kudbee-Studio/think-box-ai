terraform {
  required_providers {
    upcloud = {
      source  = "UpCloudLtd/upcloud"
      version = "~> 5.0"
    }
  }
}

variable "upcloud_api_token" {
  type      = string
  sensitive = true
}

variable "kilo_public_key" {
  type    = string
  default = "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAILZ6oDsNJowkIO3rrU7EbqvSvifZZTEKKfW44hotnZBc kilo-agent@kudbee"
}

provider "upcloud" {
  username = "api_token"
  password = var.upcloud_api_token
}

# Data source: existing GPU server
data "upcloud_server" "gpu" {
  uuid = "002b8e55-1d81-4b3a-aff5-c15b2df0e66f"
}

# Data source: existing GPU storage
data "upcloud_storage" "gpu_disk" {
  uuid = "0158d252-660b-4d7b-ab3d-56da207f0ae1"
}

output "gpu_state" {
  value = data.upcloud_server.gpu.state
}

output "gpu_ip" {
  value = [for ip in data.upcloud_server.gpu.ip_addresses : ip if ip.access == "public"]
}

output "gpu_storage_info" {
  value = {
    uuid  = data.upcloud_storage.gpu_disk.uuid
    title = data.upcloud_storage.gpu_disk.title
    size  = data.upcloud_storage.gpu_disk.size
    state = data.upcloud_storage.gpu_disk.state
  }
}
